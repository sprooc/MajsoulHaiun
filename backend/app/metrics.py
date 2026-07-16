from dataclasses import dataclass
from time import perf_counter

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    GCCollector,
    Gauge,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    generate_latest,
)
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send


_STANDARD_HTTP_METHODS = frozenset(
    {"CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"}
)


@dataclass(frozen=True)
class ApiMetrics:
    registry: CollectorRegistry
    requests: Counter
    duration: Histogram
    in_progress: Gauge

    @classmethod
    def create(cls) -> "ApiMetrics":
        registry = CollectorRegistry()
        ProcessCollector(registry=registry)
        PlatformCollector(registry=registry)
        GCCollector(registry=registry)
        return cls(
            registry=registry,
            requests=Counter(
                "haiun_http_requests",
                "Completed Haiun API requests.",
                ("method", "route", "status"),
                registry=registry,
            ),
            duration=Histogram(
                "haiun_http_request_duration_seconds",
                "Haiun API request duration in seconds.",
                ("method", "route"),
                buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
                registry=registry,
            ),
            in_progress=Gauge(
                "haiun_http_requests_in_progress",
                "Haiun API requests currently being processed.",
                ("method",),
                registry=registry,
            ),
        )

    def response(self) -> Response:
        return Response(generate_latest(self.registry), media_type=CONTENT_TYPE_LATEST)


class ApiMetricsMiddleware:
    def __init__(self, app: ASGIApp, metrics: ApiMetrics):
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return

        raw_method = scope.get("method")
        method = raw_method if raw_method in _STANDARD_HTTP_METHODS else "OTHER"
        status = 500
        started_at = perf_counter()
        self.metrics.in_progress.labels(method=method).inc()

        async def send_with_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            route = scope.get("route")
            route_path = getattr(route, "path", None)
            if not isinstance(route_path, str) or not route_path.startswith("/api/"):
                route_path = "unmatched"
            elapsed = perf_counter() - started_at
            self.metrics.requests.labels(
                method=method,
                route=route_path,
                status=str(status),
            ).inc()
            self.metrics.duration.labels(method=method, route=route_path).observe(elapsed)
            self.metrics.in_progress.labels(method=method).dec()

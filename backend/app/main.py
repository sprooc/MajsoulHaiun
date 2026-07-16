import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.api.access import router as access_router
from app.api.analyses import router as analysis_router
from app.api.health import router as health_router
from app.api.replays import router as replay_router
from app.api.sources import router as source_router
from app.algorithms.baseline_v1 import BaselineV1
from app.algorithms.registry import AlgorithmRegistry
from app.auth import AdminLoginLimiter
from app.config import REPOSITORY_ROOT, Settings
from app.config_file import HaiunConfigError, HaiunFileConfig, load_haiun_config
from app.db import create_session_factory
from app.errors import AppError
from app.metrics import ApiMetrics, ApiMetricsMiddleware
from app.migrations import upgrade_database
from app.sources.amae_koromo import AmaeKoromoSource
from app.sources.registry import SourceRegistry
from app import models  # noqa: F401


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if (
                exc.status_code != 404
                or path == "api"
                or path.startswith("api/")
                or scope["method"] not in ("GET", "HEAD")
                or "." in path.rsplit("/", 1)[-1]
                or "text/html" not in Headers(scope=scope).get("accept", "").lower()
            ):
                raise
            return await super().get_response("index.html", scope)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    resolved.data_dir.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        await asyncio.to_thread(upgrade_database, resolved.database_url)
        engine = application.state.session_factory.kw["bind"]
        yield
        await application.state.http_client.aclose()
        await engine.dispose()

    app = FastAPI(title="牌运 Haiun", version=resolved.version, lifespan=lifespan)
    if resolved.metrics_enabled:
        metrics = ApiMetrics.create()
        app.state.metrics = metrics
        app.add_middleware(ApiMetricsMiddleware, metrics=metrics)

        @app.get("/metrics", include_in_schema=False)
        def prometheus_metrics() -> Response:
            return metrics.response()

    app.state.settings = resolved
    try:
        app.state.file_config = load_haiun_config(resolved.config_path, missing_ok=True)
    except HaiunConfigError:
        app.state.file_config = HaiunFileConfig()
    app.state.admin_login_limiter = AdminLoginLimiter()
    app.state.session_factory = create_session_factory(resolved.database_url)
    app.state.http_client = httpx.AsyncClient()
    source_registry = SourceRegistry()
    source_registry.register(AmaeKoromoSource(app.state.http_client))
    app.state.source_registry = source_registry
    algorithm_registry = AlgorithmRegistry()
    algorithm_registry.register(BaselineV1())
    app.state.algorithm_registry = algorithm_registry

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "parameters": exc.parameters},
        )
    if resolved.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved.allowed_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type"],
        )
    app.include_router(health_router)
    app.include_router(access_router)
    app.include_router(analysis_router)
    app.include_router(source_router)
    app.include_router(replay_router)
    static_directory = REPOSITORY_ROOT / "frontend" / "dist"
    if static_directory.is_dir():
        app.mount("/", SPAStaticFiles(directory=static_directory, html=True), name="frontend")
    return app


app = create_app()

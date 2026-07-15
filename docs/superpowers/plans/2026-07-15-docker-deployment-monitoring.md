# Docker Deployment and Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-container Docker mode and a port-80 Nginx production mode with a memory-bounded Grafana, Loki, Prometheus, and Alloy monitoring stack for API traffic and backend process health.

**Architecture:** Build one repository-shaped Python image containing the compiled Vite frontend, then reuse it from two standalone Compose files. Simple mode publishes Haiun directly on port 8765; production publishes only Nginx on port 80, keeps Grafana on loopback, sends structured Nginx API logs to a same-network-namespace Alloy receiver, and exposes normalized FastAPI metrics only to internal Prometheus.

**Tech Stack:** Docker Engine 28+, Docker Compose 2.40+, Python 3.13 slim, uv 0.11.26, Node.js 22, Nginx 1.29 Alpine, `prometheus-client`, Prometheus 3.5.0, Loki 3.5.1, Grafana Alloy 1.10.1, Grafana 12.1.0, FastAPI, pytest, Bash, JSON, YAML, and Grafana dashboard provisioning.

## Global Constraints

- The Chinese product name is **牌运** and **Haiun** is the Japanese reading of “牌運”.
- Preserve existing Chinese and English terminology and keep recursive locale key trees identical if locale resources are touched; this plan does not require locale changes.
- Never request, copy, log, store in monitoring, or transmit Mahjong Soul passwords, OAuth tokens, verification codes, or browser sessions.
- Never include `config/config.toml`, `data/`, `.env`, or `secrets/` in an image layer.
- Nginx access data must exclude request bodies, query strings, cookies, authorization headers, and raw referrer paths, queries, or fragments.
- Opponents' voluntary discards remain informational `opponent_gift` events and do not contribute to the main luck score; deployment work must not touch scoring code.
- Preserve three-player rules, including excluding 2–8 manzu tiles and supporting kita; deployment work must not touch rule code.
- Production Nginx publishes exactly `80:80`; the Docker stack does not terminate TLS.
- Grafana publishes only `127.0.0.1:3000:3000`; Haiun, Prometheus, Loki, and Alloy publish no production host ports.
- Monitoring retention is 30 days, with no IP geolocation, Alertmanager, cAdvisor, or node exporter.
- Production starts one Uvicorn worker and uses these memory limits: Haiun 768 MiB, Grafana 192 MiB, Loki 192 MiB, Prometheus 192 MiB, Alloy 96 MiB, and Nginx 64 MiB.
- Preserve unrelated work. `AGENTS.md` is currently staged by the user, so every task commit must use `git commit --only <task paths>` and leave that staged change untouched.
- Follow test-driven development: add a failing check, run it to confirm failure, implement the smallest complete behavior, rerun the check, and commit.

---

## File Structure

### Backend metrics

- `backend/app/metrics.py`: owns one per-application Prometheus registry, API-only ASGI instrumentation, normalized route labels, and the text exposition response.
- `backend/app/config.py`: adds the disabled-by-default `metrics_enabled` setting.
- `backend/app/main.py`: conditionally installs the metrics middleware and schema-hidden `/metrics` endpoint before static mounting.
- `backend/tests/api/test_metrics.py`: verifies enablement, API-only collection, route normalization, and secret-free output.
- `pyproject.toml` and `uv.lock`: add and lock `prometheus-client>=0.22,<1`.

### Application container and simple mode

- `Dockerfile`: builds the frontend, creates a locked Python runtime, preserves the repository layout, and runs Haiun as a non-root user.
- `.dockerignore`: excludes local builds, data, configuration, secrets, tests, and development-only files from the build context.
- `compose.simple.yml`: publishes one Haiun container on port 8765 with shared named data storage and read-only configuration.
- `scripts/check_docker_deploy.sh`: validates image/Compose files and performs isolated smoke tests without using the operator's real configuration or data volume.

### Production edge and telemetry

- `deploy/nginx/nginx.conf`: global worker, log format, referrer sanitization, rate-limit zone, and trusted-proxy include.
- `deploy/nginx/conf.d/haiun.conf`: port-80 server, proxy headers, metrics denial, upload limit, API rate limit, and UDP syslog access logging.
- `deploy/nginx/trusted-proxies.default.conf`: safe loopback and RFC1918 trusted proxy networks.
- `deploy/alloy/config.alloy`: receives Nginx RFC3164 UDP syslog on loopback and writes it to Loki with stable labels.
- `deploy/loki/config.yml`: single-node filesystem TSDB storage with 720-hour retention and compaction.
- `deploy/prometheus/prometheus.yml`: scrapes Haiun every 30 seconds.
- `deploy/grafana/provisioning/datasources/haiun.yml`: provisions fixed-UID Prometheus and Loki data sources.
- `deploy/grafana/provisioning/dashboards/haiun.yml`: provisions version-controlled dashboards.
- `deploy/grafana/dashboards/haiun-api-overview.json`: request rate, errors, latency, in-progress requests, and route traffic.
- `deploy/grafana/dashboards/haiun-access-sources.json`: source IP, referrer host, user-agent, recent, slow, and failed requests.
- `deploy/grafana/dashboards/haiun-backend-runtime.json`: process CPU, memory, GC, uptime, and scrape health.
- `compose.production.yml`: integrates Nginx, Haiun, Alloy, Loki, Prometheus, Grafana, networks, secrets, health checks, persistent volumes, and resource limits.

### Operator documentation

- `.env.docker.example`: documents non-secret volume, config, image, and trusted-proxy overrides.
- `.gitignore`: ignores the Grafana secret directory.
- `README.md`: documents prerequisites, both modes, TLS-proxy assumptions, trusted proxy configuration, Grafana access, resource tuning, backup/restore, upgrade, and verification.

---

### Task 1: Add API-Only Prometheus Instrumentation

**Files:**
- Create: `backend/app/metrics.py`
- Create: `backend/tests/api/test_metrics.py`
- Modify: `backend/app/config.py:18-26`
- Modify: `backend/app/main.py:49-99`
- Modify: `pyproject.toml:11-24`
- Modify: `uv.lock`

**Interfaces:**
- Produces: `Settings.metrics_enabled: bool`, default `False`, environment key `HAIUN_METRICS_ENABLED`.
- Produces: `ApiMetrics.create() -> ApiMetrics` with a private `CollectorRegistry` per app instance.
- Produces: `ApiMetricsMiddleware(app: ASGIApp, metrics: ApiMetrics)` that observes only HTTP paths beginning `/api/`.
- Produces: `ApiMetrics.response() -> starlette.responses.Response` containing Prometheus text format.
- Produces metric families `haiun_http_requests_total`, `haiun_http_request_duration_seconds`, and `haiun_http_requests_in_progress`.
- Consumes: matched Starlette/FastAPI route objects from `scope["route"]`; dynamic raw URLs must never become labels.

- [ ] **Step 1: Add the dependency declaration and lock it**

Add this line to the main dependency array in `pyproject.toml`:

```toml
  "prometheus-client>=0.22,<1",
```

Run:

```bash
nix develop -c uv lock
nix develop -c uv sync --extra test
```

Expected: `uv.lock` contains one `prometheus-client` package entry, the `haiun` package dependency list references it, and the existing `.venv` can import `prometheus_client`.

- [ ] **Step 2: Write failing metrics tests**

Create `backend/tests/api/test_metrics.py` with these cases:

```python
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_metrics_are_disabled_by_default(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        response = client.get("/metrics")

    assert response.status_code == 404


def test_metrics_setting_accepts_environment_override(monkeypatch):
    monkeypatch.setenv("HAIUN_METRICS_ENABLED", "true")

    assert Settings().metrics_enabled is True


def test_enabled_metrics_are_schema_hidden_and_include_process_metrics(tmp_path):
    with TestClient(
        create_app(Settings(data_dir=tmp_path, metrics_enabled=True))
    ) as client:
        metrics_response = client.get("/metrics")
        schema_response = client.get("/openapi.json")

    assert metrics_response.status_code == 200
    assert "process_resident_memory_bytes" in metrics_response.text
    assert "/metrics" not in schema_response.json()["paths"]


def test_metrics_observe_only_api_requests(tmp_path):
    with TestClient(
        create_app(Settings(data_dir=tmp_path, metrics_enabled=True))
    ) as client:
        client.get("/", headers={"Accept": "text/html"})
        metrics = client.get("/metrics").text

    assert "haiun_http_requests_total" not in metrics


def test_metrics_use_normalized_routes_and_exclude_request_secrets(tmp_path):
    submission_id = uuid4()
    with TestClient(
        create_app(Settings(data_dir=tmp_path, metrics_enabled=True))
    ) as client:
        response = client.get(
            f"/api/results/{submission_id}",
            params={"oauth_token": "must-not-be-exported"},
            cookies={"haiun_admin_session": "must-not-be-exported"},
        )
        metrics = client.get("/metrics").text

    assert response.status_code == 404
    assert 'route="/api/results/{submission_id}"' in metrics
    assert 'status="404"' in metrics
    assert str(submission_id) not in metrics
    assert "must-not-be-exported" not in metrics
    assert "oauth_token" not in metrics
    assert "haiun_admin_session" not in metrics
```

- [ ] **Step 3: Run the metrics tests and verify RED**

Run:

```bash
nix develop -c .venv/bin/python -m pytest backend/tests/api/test_metrics.py -v
```

Expected: failures because `Settings.metrics_enabled`, conditional `/metrics`, and API instrumentation do not exist.

- [ ] **Step 4: Add the settings flag**

Add this field after `allowed_origins` in `backend/app/config.py`:

```python
    metrics_enabled: bool = False
```

- [ ] **Step 5: Implement the private registry and ASGI middleware**

Create `backend/app/metrics.py`:

```python
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

        method = scope.get("method", "UNKNOWN")
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
```

- [ ] **Step 6: Wire conditional instrumentation into the application factory**

Add these imports to `backend/app/main.py`:

```python
from app.metrics import ApiMetrics, ApiMetricsMiddleware
```

Immediately after constructing `app = FastAPI(...)`, add:

```python
    if resolved.metrics_enabled:
        metrics = ApiMetrics.create()
        app.state.metrics = metrics
        app.add_middleware(ApiMetricsMiddleware, metrics=metrics)

        @app.get("/metrics", include_in_schema=False)
        def prometheus_metrics() -> Response:
            return metrics.response()
```

Keep this block before router inclusion and before the static frontend mount. Do not add `/metrics` to any router and do not enable it by default.

- [ ] **Step 7: Run focused metrics and security tests**

Run:

```bash
nix develop -c .venv/bin/python -m pytest \
  backend/tests/api/test_metrics.py \
  backend/tests/api/test_health.py \
  backend/tests/api/test_security.py -v
```

Expected: all tests pass; `/metrics` is absent by default, present only when enabled, and exports no raw request values.

- [ ] **Step 8: Commit only the metrics task files**

Run:

```bash
git add backend/app/metrics.py backend/app/config.py backend/app/main.py \
  backend/tests/api/test_metrics.py pyproject.toml uv.lock
git commit --only \
  backend/app/metrics.py backend/app/config.py backend/app/main.py \
  backend/tests/api/test_metrics.py pyproject.toml uv.lock \
  -m "feat: add internal API metrics"
```

Expected: the task commit excludes the user's staged `AGENTS.md` change.

---

### Task 2: Build the Application Image and Simple Compose Mode

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `compose.simple.yml`
- Create: `scripts/check_docker_deploy.sh`

**Interfaces:**
- Consumes: `HAIUN_METRICS_ENABLED=false` default from Task 1.
- Produces image: `${HAIUN_IMAGE:-haiun:local}` exposing internal port 8765 and running one non-root Uvicorn worker.
- Produces Compose inputs: `HAIUN_SIMPLE_PORT`, `HAIUN_DATA_VOLUME`, `HAIUN_CONFIG_DIR`, and `HAIUN_IMAGE`.
- Produces named volume default: `haiun-data`, shared later by production mode.
- Produces check entry point: `scripts/check_docker_deploy.sh simple`.

- [ ] **Step 1: Write the failing simple-mode deployment check**

Create `scripts/check_docker_deploy.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

mode="${1:-all}"

check_simple_config() {
  docker build --tag haiun-check:app .
  docker compose -f compose.simple.yml config >/dev/null
  HAIUN_SIMPLE_PORT=18765 \
  HAIUN_DATA_VOLUME=haiun-check-simple-data \
  HAIUN_CONFIG_DIR="$root/config" \
  HAIUN_IMAGE=haiun-check:app \
    docker compose -f compose.simple.yml config --format json |
    python3 -c '
import json, sys
config = json.load(sys.stdin)
service = config["services"]["haiun"]
assert service["ports"][0]["published"] == "18765"
assert service["ports"][0]["target"] == 8765
assert service["environment"]["HAIUN_METRICS_ENABLED"] == "false"
assert service["restart"] == "unless-stopped"
'
}

smoke_simple() (
  set -euo pipefail
  project="haiun-check-simple-$$"
  port="${HAIUN_SIMPLE_TEST_PORT:-18765}"
  config_dir="$(mktemp -d)"
  cleanup() {
    HAIUN_SIMPLE_PORT="$port" \
    HAIUN_DATA_VOLUME="${project}-data" \
    HAIUN_CONFIG_DIR="$config_dir" \
    HAIUN_IMAGE=haiun-check:app \
      docker compose -p "$project" -f compose.simple.yml down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$config_dir"
  }
  trap cleanup EXIT

  HAIUN_SIMPLE_PORT="$port" \
  HAIUN_DATA_VOLUME="${project}-data" \
  HAIUN_CONFIG_DIR="$config_dir" \
  HAIUN_IMAGE=haiun-check:app \
    docker compose -p "$project" -f compose.simple.yml up -d --no-build

  curl --fail --silent --show-error --retry 30 --retry-delay 1 --retry-connrefused \
    "http://127.0.0.1:${port}/api/health" |
    python3 -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ok"'
)

case "$mode" in
  simple)
    check_simple_config
    smoke_simple
    ;;
  all)
    check_simple_config
    smoke_simple
    ;;
  *)
    printf 'Usage: %s [simple|all]\n' "$0" >&2
    exit 2
    ;;
esac
```

Make it executable:

```bash
chmod +x scripts/check_docker_deploy.sh
```

- [ ] **Step 2: Run the deployment check and verify RED**

Run:

```bash
scripts/check_docker_deploy.sh simple
```

Expected: failure because `Dockerfile` and `compose.simple.yml` do not exist.

- [ ] **Step 3: Add the build-context exclusions**

Create `.dockerignore`:

```dockerignore
.git
.github
.direnv
.env
.venv
__pycache__
*.py[cod]
*.egg-info
.pytest_cache
node_modules
frontend/node_modules
frontend/dist
frontend/test-results
frontend/playwright-report
frontend/*.js
frontend/*.d.ts
frontend/*.tsbuildinfo
backend/tests
docs
data
result
config/config.toml
secrets
```

- [ ] **Step 4: Add the multi-stage non-root application image**

Create `Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend \
    HAIUN_DATA_DIR=/data \
    HAIUN_CONFIG=/app/config/config.toml

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY backend/ ./backend/
RUN uv sync --frozen --no-dev --no-editable
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

RUN groupadd --system --gid 10001 haiun \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --no-create-home haiun \
    && mkdir -p /data /app/config \
    && chown -R haiun:haiun /data /app

USER haiun
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=3).read()"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
```

The repository-shaped `/app/backend`, `/app/backend/alembic`, and `/app/frontend/dist` paths are required by the current migration and static-file path resolution code.

- [ ] **Step 5: Add the standalone simple Compose file**

Create `compose.simple.yml`:

```yaml
services:
  haiun:
    image: ${HAIUN_IMAGE:-haiun:local}
    build:
      context: .
      target: runtime
    environment:
      HAIUN_CONFIG: /app/config/config.toml
      HAIUN_DATA_DIR: /data
      HAIUN_METRICS_ENABLED: "${HAIUN_METRICS_ENABLED:-false}"
    ports:
      - "${HAIUN_SIMPLE_PORT:-8765}:8765"
    volumes:
      - type: volume
        source: haiun-data
        target: /data
      - type: bind
        source: ${HAIUN_CONFIG_DIR:-./config}
        target: /app/config
        read_only: true
    restart: unless-stopped
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=3).read()
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3

volumes:
  haiun-data:
    name: ${HAIUN_DATA_VOLUME:-haiun-data}
```

With no environment override, the published port resolves to exactly `8765:8765`.

- [ ] **Step 6: Run syntax, build, configuration, and smoke checks**

Run:

```bash
bash -n scripts/check_docker_deploy.sh
shellcheck scripts/check_docker_deploy.sh
scripts/check_docker_deploy.sh simple
```

Expected: the image builds, Compose resolves port 18765 in the isolated check, `/api/health` returns `{"status":"ok",...}`, and cleanup removes the test container and volume.

- [ ] **Step 7: Confirm secrets and local data are absent from the image**

Run:

```bash
docker run --rm --entrypoint /bin/sh haiun-check:app -c '
  test ! -e /app/config/config.toml
  test ! -e /app/data
  test ! -e /app/secrets
  test -f /app/frontend/dist/index.html
  test -f /app/backend/alembic.ini
'
```

Expected: exit status 0 and no output.

- [ ] **Step 8: Commit only the simple deployment files**

Run:

```bash
git add Dockerfile .dockerignore compose.simple.yml scripts/check_docker_deploy.sh
git commit --only Dockerfile .dockerignore compose.simple.yml scripts/check_docker_deploy.sh \
  -m "feat: add simple Docker deployment"
```

---

### Task 3: Add the Nginx Production Edge

**Files:**
- Create: `deploy/nginx/nginx.conf`
- Create: `deploy/nginx/conf.d/haiun.conf`
- Create: `deploy/nginx/trusted-proxies.default.conf`
- Modify: `scripts/check_docker_deploy.sh`

**Interfaces:**
- Produces: Nginx listener `0.0.0.0:80` with upstream `haiun:8765`.
- Produces: internal UDP RFC3164 syslog target `127.0.0.1:1514`, consumed by Alloy sharing Nginx's network namespace in Task 6.
- Produces: JSON log fields `timestamp`, `request_id`, `client_ip`, `proxy_ip`, `forwarded_for`, `method`, `uri`, `status`, `bytes`, `request_time`, `upstream_response_time`, `referrer_host`, and `user_agent`.
- Produces: trusted proxy include path `/etc/nginx/trusted-proxies.conf`.
- Produces: API rate limit 10 requests/second per resolved client with burst 20 and HTTP 429.

- [ ] **Step 1: Extend the check script with a failing Nginx validator**

Add this function before the `case` statement in `scripts/check_docker_deploy.sh`:

```bash
check_nginx_config() {
  docker run --rm \
    --add-host haiun:127.0.0.1 \
    --volume "$root/deploy/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
    --volume "$root/deploy/nginx/conf.d:/etc/nginx/conf.d:ro" \
    --volume "$root/deploy/nginx/trusted-proxies.default.conf:/etc/nginx/trusted-proxies.conf:ro" \
    nginx:1.29-alpine nginx -t

  python3 - <<'PY'
from pathlib import Path

text = Path("deploy/nginx/conf.d/haiun.conf").read_text(encoding="utf-8")
assert "listen 80" in text
assert "client_max_body_size 32m" in text
assert "limit_req zone=haiun_api burst=20 nodelay" in text
assert "access_log syslog:server=127.0.0.1:1514" in text
assert "location = /metrics" in text
assert "return 404" in text
PY
}
```

Extend the mode dispatch to accept `nginx` and call `check_nginx_config` from `all`:

```bash
  nginx)
    check_nginx_config
    ;;
```

Update the usage text to `Usage: %s [simple|nginx|all]`.

- [ ] **Step 2: Run the Nginx check and verify RED**

Run:

```bash
scripts/check_docker_deploy.sh nginx
```

Expected: failure because the Nginx configuration files do not exist.

- [ ] **Step 3: Add the trusted proxy defaults**

Create `deploy/nginx/trusted-proxies.default.conf`:

```nginx
set_real_ip_from 127.0.0.1;
set_real_ip_from 10.0.0.0/8;
set_real_ip_from 172.16.0.0/12;
set_real_ip_from 192.168.0.0/16;
real_ip_header X-Forwarded-For;
real_ip_recursive on;
```

These defaults do not trust arbitrary public senders. Operators whose TLS proxy uses public source networks must mount an explicit replacement file and firewall port 80 to those networks.

- [ ] **Step 4: Add the global Nginx configuration**

Create `deploy/nginx/nginx.conf`:

```nginx
user nginx;
worker_processes 1;
error_log /dev/stderr warn;
pid /var/run/nginx.pid;

events {
    worker_connections 512;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    include /etc/nginx/trusted-proxies.conf;

    map $http_x_forwarded_proto $haiun_forwarded_proto {
        default $http_x_forwarded_proto;
        "" $scheme;
    }

    map $http_referer $haiun_referrer_host {
        default "";
        ~^https?://(?<haiun_ref_host>[^/:?#]+) $haiun_ref_host;
    }

    log_format haiun_api_json escape=json
        '{'
        '"timestamp":"$time_iso8601",'
        '"request_id":"$request_id",'
        '"client_ip":"$remote_addr",'
        '"proxy_ip":"$realip_remote_addr",'
        '"forwarded_for":"$http_x_forwarded_for",'
        '"method":"$request_method",'
        '"uri":"$uri",'
        '"status":$status,'
        '"bytes":$body_bytes_sent,'
        '"request_time":$request_time,'
        '"upstream_response_time":"$upstream_response_time",'
        '"referrer_host":"$haiun_referrer_host",'
        '"user_agent":"$http_user_agent"'
        '}';

    limit_req_zone $binary_remote_addr zone=haiun_api:10m rate=10r/s;

    access_log off;
    sendfile on;
    keepalive_timeout 65;
    server_tokens off;

    include /etc/nginx/conf.d/*.conf;
}
```

- [ ] **Step 5: Add the port-80 Haiun server**

Create `deploy/nginx/conf.d/haiun.conf`:

```nginx
upstream haiun_backend {
    server haiun:8765;
    keepalive 8;
}

server {
    listen 80 default_server;
    server_name _;

    client_max_body_size 32m;
    limit_req_status 429;

    location = /nginx-health {
        access_log off;
        default_type text/plain;
        return 200 "ok\n";
    }

    location = /metrics {
        access_log off;
        return 404;
    }

    location /api/ {
        limit_req zone=haiun_api burst=20 nodelay;
        access_log syslog:server=127.0.0.1:1514,facility=local7,tag=haiun_api,severity=info haiun_api_json;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Request-ID $request_id;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $haiun_forwarded_proto;
        proxy_read_timeout 120s;
        proxy_pass http://haiun_backend;
    }

    location / {
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Request-ID $request_id;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $haiun_forwarded_proto;
        proxy_read_timeout 120s;
        proxy_pass http://haiun_backend;
    }
}
```

- [ ] **Step 6: Run Nginx validation**

Run:

```bash
bash -n scripts/check_docker_deploy.sh
shellcheck scripts/check_docker_deploy.sh
scripts/check_docker_deploy.sh nginx
```

Expected: `nginx: configuration file /etc/nginx/nginx.conf test is successful` and all static assertions pass.

- [ ] **Step 7: Verify the log format excludes forbidden request data**

Run:

```bash
if rg -n '\$args|\$request_uri|\$request_body|\$http_cookie|\$http_authorization' \
  deploy/nginx; then
  exit 1
fi
```

Expected: exit status 0 with no matches.

- [ ] **Step 8: Commit only the Nginx task files**

Run:

```bash
git add deploy/nginx scripts/check_docker_deploy.sh
git commit --only deploy/nginx scripts/check_docker_deploy.sh \
  -m "feat: add production Nginx edge"
```

---

### Task 4: Add Alloy, Loki, and Prometheus Configuration

**Files:**
- Create: `deploy/alloy/config.alloy`
- Create: `deploy/loki/config.yml`
- Create: `deploy/prometheus/prometheus.yml`
- Modify: `scripts/check_docker_deploy.sh`

**Interfaces:**
- Consumes: Nginx RFC3164 UDP syslog at `127.0.0.1:1514` from Task 3.
- Produces: Loki write endpoint `http://loki:3100/loki/api/v1/push`.
- Produces stable log labels: `service="haiun"`, `environment="production"`, and `log_type="api_access"`.
- Produces: Prometheus scrape jobs `haiun`, `prometheus`, `loki`, and `alloy` every 30 seconds; Alloy is reached at `nginx:12345` because it shares Nginx networking.
- Produces: Loki 720-hour retention and Prometheus runtime flags for 30 days plus a 512 MiB storage cap, wired in Task 6.

- [ ] **Step 1: Extend the check script with failing telemetry validators**

Add this function before the mode dispatch in `scripts/check_docker_deploy.sh`:

```bash
check_telemetry_config() {
  docker run --rm \
    --volume "$root/deploy/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
    --entrypoint /bin/promtool \
    prom/prometheus:v3.5.0 \
    check config /etc/prometheus/prometheus.yml

  docker run --rm \
    --volume "$root/deploy/loki/config.yml:/etc/loki/config.yml:ro" \
    grafana/loki:3.5.1 \
    -config.file=/etc/loki/config.yml -verify-config=true

  docker run --rm \
    --volume "$root/deploy/alloy/config.alloy:/etc/alloy/config.alloy:ro" \
    grafana/alloy:v1.10.1 \
    validate /etc/alloy/config.alloy
}
```

Add a `telemetry)` mode that runs `check_telemetry_config`, call it from `all`, and update the usage text to `Usage: %s [simple|nginx|telemetry|all]`.

- [ ] **Step 2: Run the telemetry validation and verify RED**

Run:

```bash
scripts/check_docker_deploy.sh telemetry
```

Expected: failure because the Alloy, Loki, and Prometheus files do not exist.

- [ ] **Step 3: Add the Alloy syslog-to-Loki pipeline**

Create `deploy/alloy/config.alloy`:

```alloy
logging {
  level = "warn"
}

loki.source.syslog "nginx" {
  listener {
    address       = "127.0.0.1:1514"
    protocol      = "udp"
    syslog_format = "rfc3164"
    labels = {
      service     = "haiun",
      environment = "production",
      log_type    = "api_access",
    }
  }

  forward_to = [loki.write.local.receiver]
}

loki.write "local" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```

Do not promote client IP, URI, user-agent, referrer, or request ID to labels. They remain inside the JSON log line and are parsed in Loki queries.

- [ ] **Step 4: Add single-node Loki storage and retention**

Create `deploy/loki/config.yml`:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096
  log_level: warn

common:
  path_prefix: /loki
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 720h
  allow_structured_metadata: true

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  delete_request_store: filesystem
```

- [ ] **Step 5: Add the internal Prometheus scrape job**

Create `deploy/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 30s
  evaluation_interval: 30s

scrape_configs:
  - job_name: haiun
    metrics_path: /metrics
    static_configs:
      - targets:
          - haiun:8765

  - job_name: prometheus
    static_configs:
      - targets:
          - 127.0.0.1:9090

  - job_name: loki
    static_configs:
      - targets:
          - loki:3100

  - job_name: alloy
    static_configs:
      - targets:
          - nginx:12345
```

- [ ] **Step 6: Run all telemetry validators**

Run:

```bash
bash -n scripts/check_docker_deploy.sh
shellcheck scripts/check_docker_deploy.sh
scripts/check_docker_deploy.sh telemetry
```

Expected: Prometheus reports `SUCCESS`, Loki exits successfully after config verification, and Alloy reports a valid configuration.

- [ ] **Step 7: Commit only the telemetry configuration**

Run:

```bash
git add deploy/alloy deploy/loki deploy/prometheus scripts/check_docker_deploy.sh
git commit --only deploy/alloy deploy/loki deploy/prometheus scripts/check_docker_deploy.sh \
  -m "feat: add production telemetry storage"
```

---

### Task 5: Provision Grafana Data Sources and Dashboards

**Files:**
- Create: `deploy/grafana/provisioning/datasources/haiun.yml`
- Create: `deploy/grafana/provisioning/dashboards/haiun.yml`
- Create: `deploy/grafana/dashboards/haiun-api-overview.json`
- Create: `deploy/grafana/dashboards/haiun-access-sources.json`
- Create: `deploy/grafana/dashboards/haiun-backend-runtime.json`
- Modify: `scripts/check_docker_deploy.sh`

**Interfaces:**
- Consumes: Prometheus URL `http://prometheus:9090` and Loki URL `http://loki:3100`.
- Produces fixed data-source UIDs `prometheus` and `loki`, used verbatim by dashboard JSON.
- Produces dashboard UIDs `haiun-api-overview`, `haiun-access-sources`, and `haiun-backend-runtime`.
- Consumes metrics from Task 1 and stable Loki labels from Task 4.
- Produces check entry point: `scripts/check_docker_deploy.sh grafana`.

- [ ] **Step 1: Extend the check script with failing Grafana assertions**

Add this function before the mode dispatch in `scripts/check_docker_deploy.sh`:

```bash
check_grafana_config() {
  python3 - <<'PY'
import json
from pathlib import Path

dashboard_dir = Path("deploy/grafana/dashboards")
expected = {
    "haiun-api-overview.json": ("haiun-api-overview", "Haiun API Overview"),
    "haiun-access-sources.json": ("haiun-access-sources", "Haiun Access Sources"),
    "haiun-backend-runtime.json": ("haiun-backend-runtime", "Haiun Backend Runtime"),
}
for filename, (uid, title) in expected.items():
    dashboard = json.loads((dashboard_dir / filename).read_text(encoding="utf-8"))
    assert dashboard["uid"] == uid
    assert dashboard["title"] == title
    assert dashboard["refresh"] == "30s"
    assert dashboard["panels"]

all_text = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted(dashboard_dir.glob("*.json"))
)
for required in (
    "haiun_http_requests_total",
    "haiun_http_request_duration_seconds_bucket",
    "process_resident_memory_bytes",
    'service=\\"haiun\\"',
    'log_type=\\"api_access\\"',
):
    assert required in all_text

for forbidden in ("oauth_token", "haiun_admin_session", "request_body", "authorization"):
    assert forbidden not in all_text.lower()

datasources = Path(
    "deploy/grafana/provisioning/datasources/haiun.yml"
).read_text(encoding="utf-8")
assert "uid: prometheus" in datasources
assert "url: http://prometheus:9090" in datasources
assert "uid: loki" in datasources
assert "url: http://loki:3100" in datasources

providers = Path(
    "deploy/grafana/provisioning/dashboards/haiun.yml"
).read_text(encoding="utf-8")
assert "path: /var/lib/grafana/dashboards" in providers
PY
}
```

Add a `grafana)` mode that runs `check_grafana_config`, call it from `all`, and update the usage text to `Usage: %s [simple|nginx|telemetry|grafana|all]`.

- [ ] **Step 2: Run the Grafana check and verify RED**

Run:

```bash
scripts/check_docker_deploy.sh grafana
```

Expected: failure because the provisioning and dashboard files do not exist.

- [ ] **Step 3: Add fixed-UID data-source provisioning**

Create `deploy/grafana/provisioning/datasources/haiun.yml`:

```yaml
apiVersion: 1

deleteDatasources:
  - name: Prometheus
    orgId: 1
  - name: Loki
    orgId: 1

datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: 30s

  - name: Loki
    uid: loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false
```

- [ ] **Step 4: Add dashboard-provider provisioning**

Create `deploy/grafana/provisioning/dashboards/haiun.yml`:

```yaml
apiVersion: 1

providers:
  - name: Haiun
    orgId: 1
    folder: Haiun
    type: file
    disableDeletion: true
    allowUiUpdates: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
```

- [ ] **Step 5: Add the API overview dashboard**

Create `deploy/grafana/dashboards/haiun-api-overview.json`:

```json
{
  "annotations": {"list": []},
  "editable": false,
  "graphTooltip": 0,
  "panels": [
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"unit": "reqps"}, "overrides": []},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
      "id": 1,
      "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "single"}},
      "targets": [{"expr": "sum(rate(haiun_http_requests_total[5m]))", "legendFormat": "requests", "refId": "A"}],
      "title": "Requests per second",
      "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"unit": "percentunit", "min": 0, "max": 1}, "overrides": []},
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
      "id": 2,
      "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "single"}},
      "targets": [{"expr": "sum(rate(haiun_http_requests_total{status=~\"5..\"}[5m])) / clamp_min(sum(rate(haiun_http_requests_total[5m])), 1)", "legendFormat": "5xx rate", "refId": "A"}],
      "title": "Server error rate",
      "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"unit": "s"}, "overrides": []},
      "gridPos": {"h": 8, "w": 16, "x": 0, "y": 8},
      "id": 3,
      "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "single"}},
      "targets": [
        {"expr": "histogram_quantile(0.50, sum by (le) (rate(haiun_http_request_duration_seconds_bucket[5m])))", "legendFormat": "p50", "refId": "A"},
        {"expr": "histogram_quantile(0.95, sum by (le) (rate(haiun_http_request_duration_seconds_bucket[5m])))", "legendFormat": "p95", "refId": "B"},
        {"expr": "histogram_quantile(0.99, sum by (le) (rate(haiun_http_request_duration_seconds_bucket[5m])))", "legendFormat": "p99", "refId": "C"}
      ],
      "title": "API latency",
      "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []},
      "gridPos": {"h": 8, "w": 8, "x": 16, "y": 8},
      "id": 4,
      "options": {"colorMode": "value", "graphMode": "area", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "values": false}},
      "targets": [{"expr": "sum(haiun_http_requests_in_progress)", "refId": "A"}],
      "title": "Requests in progress",
      "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"unit": "reqps"}, "overrides": []},
      "gridPos": {"h": 9, "w": 24, "x": 0, "y": 16},
      "id": 5,
      "options": {"legend": {"displayMode": "table", "placement": "right"}, "tooltip": {"mode": "multi"}},
      "targets": [{"expr": "topk(10, sum by (method, route) (rate(haiun_http_requests_total[5m])))", "legendFormat": "{{method}} {{route}}", "refId": "A"}],
      "title": "Busiest normalized routes",
      "type": "timeseries"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 41,
  "tags": ["haiun", "api"],
  "templating": {"list": []},
  "time": {"from": "now-6h", "to": "now"},
  "timezone": "browser",
  "title": "Haiun API Overview",
  "uid": "haiun-api-overview",
  "version": 1
}
```

- [ ] **Step 6: Add the access-source dashboard**

Create `deploy/grafana/dashboards/haiun-access-sources.json`:

```json
{
  "annotations": {"list": []},
  "editable": false,
  "graphTooltip": 0,
  "panels": [
    {
      "datasource": {"type": "loki", "uid": "loki"},
      "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []},
      "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0},
      "id": 1,
      "options": {"legend": {"displayMode": "table", "placement": "right"}, "tooltip": {"mode": "single"}},
      "targets": [{"expr": "topk(10, sum by (client_ip) (count_over_time({service=\"haiun\", log_type=\"api_access\"} | json | __error__=\"\" [5m])))", "legendFormat": "{{client_ip}}", "queryType": "range", "refId": "A"}],
      "title": "Top client IPs",
      "type": "timeseries"
    },
    {
      "datasource": {"type": "loki", "uid": "loki"},
      "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []},
      "gridPos": {"h": 8, "w": 8, "x": 8, "y": 0},
      "id": 2,
      "options": {"legend": {"displayMode": "table", "placement": "right"}, "tooltip": {"mode": "single"}},
      "targets": [{"expr": "topk(10, sum by (referrer_host) (count_over_time({service=\"haiun\", log_type=\"api_access\"} | json | __error__=\"\" | referrer_host != \"\" [5m])))", "legendFormat": "{{referrer_host}}", "queryType": "range", "refId": "A"}],
      "title": "Top referrer hosts",
      "type": "timeseries"
    },
    {
      "datasource": {"type": "loki", "uid": "loki"},
      "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []},
      "gridPos": {"h": 8, "w": 8, "x": 16, "y": 0},
      "id": 3,
      "options": {"legend": {"displayMode": "table", "placement": "right"}, "tooltip": {"mode": "single"}},
      "targets": [{"expr": "topk(10, sum by (user_agent) (count_over_time({service=\"haiun\", log_type=\"api_access\"} | json | __error__=\"\" [5m])))", "legendFormat": "{{user_agent}}", "queryType": "range", "refId": "A"}],
      "title": "Top user-agents",
      "type": "timeseries"
    },
    {
      "datasource": {"type": "loki", "uid": "loki"},
      "gridPos": {"h": 10, "w": 12, "x": 0, "y": 8},
      "id": 4,
      "options": {"dedupStrategy": "none", "enableLogDetails": true, "prettifyLogMessage": true, "showCommonLabels": false, "showLabels": false, "showTime": true, "sortOrder": "Descending", "wrapLogMessage": true},
      "targets": [{"expr": "{service=\"haiun\", log_type=\"api_access\"} | json", "queryType": "range", "refId": "A"}],
      "title": "Recent API requests",
      "type": "logs"
    },
    {
      "datasource": {"type": "loki", "uid": "loki"},
      "gridPos": {"h": 10, "w": 12, "x": 12, "y": 8},
      "id": 5,
      "options": {"dedupStrategy": "none", "enableLogDetails": true, "prettifyLogMessage": true, "showCommonLabels": false, "showLabels": false, "showTime": true, "sortOrder": "Descending", "wrapLogMessage": true},
      "targets": [
        {"expr": "{service=\"haiun\", log_type=\"api_access\"} | json | __error__=\"\" | request_time > 1", "queryType": "range", "refId": "A"},
        {"expr": "{service=\"haiun\", log_type=\"api_access\"} | json | __error__=\"\" | status >= 500", "queryType": "range", "refId": "B"}
      ],
      "title": "Slow or failed requests",
      "type": "logs"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 41,
  "tags": ["haiun", "access"],
  "templating": {"list": []},
  "time": {"from": "now-6h", "to": "now"},
  "timezone": "browser",
  "title": "Haiun Access Sources",
  "uid": "haiun-access-sources",
  "version": 1
}
```

- [ ] **Step 7: Add the backend-runtime dashboard**

Create `deploy/grafana/dashboards/haiun-backend-runtime.json`:

```json
{
  "annotations": {"list": []},
  "editable": false,
  "graphTooltip": 0,
  "panels": [
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"unit": "percentunit"}, "overrides": []},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
      "id": 1,
      "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "single"}},
      "targets": [{"expr": "rate(process_cpu_seconds_total[5m])", "legendFormat": "CPU", "refId": "A"}],
      "title": "Python process CPU",
      "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"unit": "bytes"}, "overrides": []},
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
      "id": 2,
      "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "single"}},
      "targets": [{"expr": "process_resident_memory_bytes", "legendFormat": "resident memory", "refId": "A"}],
      "title": "Python process memory",
      "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"unit": "ops"}, "overrides": []},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
      "id": 3,
      "options": {"legend": {"displayMode": "table", "placement": "right"}, "tooltip": {"mode": "multi"}},
      "targets": [{"expr": "sum by (generation) (rate(python_gc_collections_total[5m]))", "legendFormat": "generation {{generation}}", "refId": "A"}],
      "title": "Garbage collections",
      "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"unit": "s"}, "overrides": []},
      "gridPos": {"h": 8, "w": 6, "x": 12, "y": 8},
      "id": 4,
      "options": {"colorMode": "value", "graphMode": "area", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "values": false}},
      "targets": [{"expr": "time() - process_start_time_seconds", "refId": "A"}],
      "title": "Process uptime",
      "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"mappings": [{"options": {"0": {"color": "red", "text": "DOWN"}, "1": {"color": "green", "text": "UP"}}, "type": "value"}], "min": 0, "max": 1}, "overrides": []},
      "gridPos": {"h": 8, "w": 6, "x": 18, "y": 8},
      "id": 5,
      "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "center", "reduceOptions": {"calcs": ["lastNotNull"], "values": false}},
      "targets": [{"expr": "up{job=\"haiun\"}", "refId": "A"}],
      "title": "Haiun scrape health",
      "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "fieldConfig": {"defaults": {"mappings": [{"options": {"0": {"color": "red", "text": "DOWN"}, "1": {"color": "green", "text": "UP"}}, "type": "value"}], "min": 0, "max": 1}, "overrides": []},
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16},
      "id": 6,
      "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "center", "orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"], "values": false}, "textMode": "value_and_name"},
      "targets": [{"expr": "up{job=~\"prometheus|loki|alloy\"}", "legendFormat": "{{job}}", "refId": "A"}],
      "title": "Monitoring service scrape health",
      "type": "stat"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 41,
  "tags": ["haiun", "runtime"],
  "templating": {"list": []},
  "time": {"from": "now-6h", "to": "now"},
  "timezone": "browser",
  "title": "Haiun Backend Runtime",
  "uid": "haiun-backend-runtime",
  "version": 1
}
```

- [ ] **Step 8: Run dashboard and provisioning validation**

Run:

```bash
bash -n scripts/check_docker_deploy.sh
shellcheck scripts/check_docker_deploy.sh
scripts/check_docker_deploy.sh grafana
```

Expected: every dashboard parses as JSON, fixed UIDs and titles match, required Prometheus and Loki queries are present, and provisioning references the correct internal URLs.

- [ ] **Step 9: Commit only the Grafana files**

Run:

```bash
git add deploy/grafana scripts/check_docker_deploy.sh
git commit --only deploy/grafana scripts/check_docker_deploy.sh \
  -m "feat: provision monitoring dashboards"
```

---

### Task 6: Integrate and Smoke-Test the Production Compose Stack

**Files:**
- Create: `compose.production.yml`
- Modify: `.gitignore`
- Modify: `scripts/check_docker_deploy.sh`

**Interfaces:**
- Consumes: the application image from Task 2, Nginx files from Task 3, telemetry configs from Task 4, and Grafana provisioning from Task 5.
- Produces production host bindings: Nginx `80:80` and Grafana `127.0.0.1:3000:3000` only.
- Produces Compose inputs: `HAIUN_IMAGE`, `HAIUN_DATA_VOLUME`, `HAIUN_CONFIG_DIR`, `HAIUN_TRUSTED_PROXIES_FILE`, `HAIUN_LOKI_VOLUME`, `HAIUN_PROMETHEUS_VOLUME`, `HAIUN_GRAFANA_VOLUME`, `HAIUN_EDGE_NETWORK`, `HAIUN_MONITORING_NETWORK`, and `GRAFANA_ADMIN_PASSWORD_FILE`.
- Produces secret: `grafana_admin_password`, read through `GF_SECURITY_ADMIN_PASSWORD__FILE`.
- Produces persistent volume defaults: `haiun-data`, `haiun-loki`, `haiun-prometheus`, and `haiun-grafana`.
- Produces network behavior: Alloy uses `network_mode: service:nginx`, so Nginx always logs to loopback UDP without depending on Alloy DNS or startup.

- [ ] **Step 1: Extend the check script with a failing production configuration check**

Add this function before the mode dispatch in `scripts/check_docker_deploy.sh`:

```bash
check_production_config() {
  docker build --tag haiun-check:app .
  HAIUN_IMAGE=haiun-check:app \
  HAIUN_DATA_VOLUME=haiun-check-data \
  HAIUN_CONFIG_DIR="$root/config" \
  HAIUN_TRUSTED_PROXIES_FILE="$root/deploy/nginx/trusted-proxies.default.conf" \
  HAIUN_LOKI_VOLUME=haiun-check-loki \
  HAIUN_PROMETHEUS_VOLUME=haiun-check-prometheus \
  HAIUN_GRAFANA_VOLUME=haiun-check-grafana \
  HAIUN_EDGE_NETWORK=haiun-check-edge \
  HAIUN_MONITORING_NETWORK=haiun-check-monitoring \
  GRAFANA_ADMIN_PASSWORD_FILE=/dev/null \
    docker compose -f compose.production.yml config --format json |
    python3 -c '
import json, sys
config = json.load(sys.stdin)
services = config["services"]

nginx_ports = services["nginx"]["ports"]
assert len(nginx_ports) == 1
assert nginx_ports[0]["published"] == "80"
assert nginx_ports[0]["target"] == 80

grafana_ports = services["grafana"]["ports"]
assert len(grafana_ports) == 1
assert grafana_ports[0]["host_ip"] == "127.0.0.1"
assert grafana_ports[0]["published"] == "3000"
assert grafana_ports[0]["target"] == 3000

for private_service in ("haiun", "prometheus", "loki", "alloy"):
    assert not services[private_service].get("ports")

expected_limits = {
    "haiun": 768 * 1024 * 1024,
    "grafana": 192 * 1024 * 1024,
    "loki": 192 * 1024 * 1024,
    "prometheus": 192 * 1024 * 1024,
    "alloy": 96 * 1024 * 1024,
    "nginx": 64 * 1024 * 1024,
}
for service, expected in expected_limits.items():
    assert services[service]["mem_limit"] == expected

assert services["alloy"]["network_mode"] == "service:nginx"
assert services["haiun"]["environment"]["HAIUN_METRICS_ENABLED"] == "true"
assert services["grafana"]["environment"]["GF_SECURITY_ADMIN_PASSWORD__FILE"] == "/run/secrets/grafana_admin_password"
prometheus_command = " ".join(services["prometheus"]["command"])
assert "--storage.tsdb.retention.time=30d" in prometheus_command
assert "--storage.tsdb.retention.size=512MB" in prometheus_command
'
}
```

Add a `production)` mode that initially runs `check_production_config`, call it from `all`, and update the usage text to `Usage: %s [simple|nginx|telemetry|grafana|production|all]`.

- [ ] **Step 2: Run the production configuration check and verify RED**

Run:

```bash
scripts/check_docker_deploy.sh production
```

Expected: failure because `compose.production.yml` does not exist.

- [ ] **Step 3: Ignore runtime secret files**

Append this entry to `.gitignore`:

```gitignore
/secrets/
```

Do not create or commit a real password file.

- [ ] **Step 4: Add the standalone production Compose file**

Create `compose.production.yml`:

```yaml
services:
  haiun:
    image: ${HAIUN_IMAGE:-haiun:local}
    build:
      context: .
      target: runtime
    command:
      - python
      - -m
      - uvicorn
      - app.main:app
      - --host
      - 0.0.0.0
      - --port
      - "8765"
      - --workers
      - "1"
      - --proxy-headers
      - --forwarded-allow-ips=*
    environment:
      HAIUN_CONFIG: /app/config/config.toml
      HAIUN_DATA_DIR: /data
      HAIUN_METRICS_ENABLED: "true"
    volumes:
      - type: volume
        source: haiun-data
        target: /data
      - type: bind
        source: ${HAIUN_CONFIG_DIR:-./config}
        target: /app/config
        read_only: true
    networks:
      - edge
    mem_limit: 768m
    restart: unless-stopped
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=3).read()
      interval: 30s
      timeout: 5s
      start_period: 30s
      retries: 3

  nginx:
    image: nginx:1.29-alpine
    depends_on:
      haiun:
        condition: service_healthy
    ports:
      - "80:80"
    volumes:
      - type: bind
        source: ./deploy/nginx/nginx.conf
        target: /etc/nginx/nginx.conf
        read_only: true
      - type: bind
        source: ./deploy/nginx/conf.d
        target: /etc/nginx/conf.d
        read_only: true
      - type: bind
        source: ${HAIUN_TRUSTED_PROXIES_FILE:-./deploy/nginx/trusted-proxies.default.conf}
        target: /etc/nginx/trusted-proxies.conf
        read_only: true
    networks:
      - edge
      - monitoring
    mem_limit: 64m
    restart: unless-stopped
    healthcheck:
      test:
        - CMD-SHELL
        - wget -qO- http://127.0.0.1/api/health >/dev/null 2>&1 || exit 1
      interval: 30s
      timeout: 5s
      start_period: 15s
      retries: 3

  alloy:
    image: grafana/alloy:v1.10.1
    network_mode: service:nginx
    depends_on:
      nginx:
        condition: service_started
      loki:
        condition: service_healthy
    command:
      - run
      - --server.http.listen-addr=0.0.0.0:12345
      - --storage.path=/var/lib/alloy/data
      - /etc/alloy/config.alloy
    volumes:
      - type: bind
        source: ./deploy/alloy/config.alloy
        target: /etc/alloy/config.alloy
        read_only: true
    mem_limit: 96m
    restart: unless-stopped
    healthcheck:
      test:
        - CMD-SHELL
        - wget -qO- http://127.0.0.1:12345/-/ready >/dev/null 2>&1 || exit 1
      interval: 30s
      timeout: 5s
      start_period: 15s
      retries: 3

  loki:
    image: grafana/loki:3.5.1
    command:
      - -config.file=/etc/loki/config.yml
    volumes:
      - type: bind
        source: ./deploy/loki/config.yml
        target: /etc/loki/config.yml
        read_only: true
      - type: volume
        source: loki-data
        target: /loki
    networks:
      - monitoring
    mem_limit: 192m
    restart: unless-stopped
    healthcheck:
      test:
        - CMD-SHELL
        - wget -qO- http://127.0.0.1:3100/ready >/dev/null 2>&1 || exit 1
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3

  prometheus:
    image: prom/prometheus:v3.5.0
    depends_on:
      haiun:
        condition: service_healthy
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --storage.tsdb.retention.time=30d
      - --storage.tsdb.retention.size=512MB
      - --web.enable-lifecycle
    volumes:
      - type: bind
        source: ./deploy/prometheus/prometheus.yml
        target: /etc/prometheus/prometheus.yml
        read_only: true
      - type: volume
        source: prometheus-data
        target: /prometheus
    networks:
      - edge
      - monitoring
    mem_limit: 192m
    restart: unless-stopped
    healthcheck:
      test:
        - CMD-SHELL
        - wget -qO- http://127.0.0.1:9090/-/ready >/dev/null 2>&1 || exit 1
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3

  grafana:
    image: grafana/grafana:12.1.0
    depends_on:
      loki:
        condition: service_healthy
      prometheus:
        condition: service_healthy
    environment:
      GF_ANALYTICS_CHECK_FOR_UPDATES: "false"
      GF_ANALYTICS_REPORTING_ENABLED: "false"
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD__FILE: /run/secrets/grafana_admin_password
      GF_USERS_ALLOW_SIGN_UP: "false"
    ports:
      - "127.0.0.1:3000:3000"
    secrets:
      - grafana_admin_password
    volumes:
      - type: volume
        source: grafana-data
        target: /var/lib/grafana
      - type: bind
        source: ./deploy/grafana/provisioning
        target: /etc/grafana/provisioning
        read_only: true
      - type: bind
        source: ./deploy/grafana/dashboards
        target: /var/lib/grafana/dashboards
        read_only: true
    networks:
      - monitoring
    mem_limit: 192m
    restart: unless-stopped
    healthcheck:
      test:
        - CMD-SHELL
        - wget -qO- http://127.0.0.1:3000/api/health >/dev/null 2>&1 || exit 1
      interval: 30s
      timeout: 5s
      start_period: 30s
      retries: 3

secrets:
  grafana_admin_password:
    file: ${GRAFANA_ADMIN_PASSWORD_FILE:-./secrets/grafana_admin_password.txt}

volumes:
  haiun-data:
    name: ${HAIUN_DATA_VOLUME:-haiun-data}
  loki-data:
    name: ${HAIUN_LOKI_VOLUME:-haiun-loki}
  prometheus-data:
    name: ${HAIUN_PROMETHEUS_VOLUME:-haiun-prometheus}
  grafana-data:
    name: ${HAIUN_GRAFANA_VOLUME:-haiun-grafana}

networks:
  edge:
    name: ${HAIUN_EDGE_NETWORK:-haiun-edge}
  monitoring:
    name: ${HAIUN_MONITORING_NETWORK:-haiun-monitoring}
    internal: true
```

The `edge` network remains a normal bridge because Haiun must make outbound requests to supported upstream replay sources. No Haiun host port is published. The `monitoring` network is internal. Alloy shares Nginx's network namespace so UDP log delivery never depends on resolving an Alloy hostname.

Monitoring services do not gate Haiun startup. Nginx depends only on a healthy Haiun service; Loki, Alloy, Prometheus, and Grafana may fail or restart without stopping the public application path.

- [ ] **Step 5: Run production Compose configuration validation**

Run:

```bash
bash -n scripts/check_docker_deploy.sh
shellcheck scripts/check_docker_deploy.sh
scripts/check_docker_deploy.sh production
```

Expected: Compose resolves exactly the two approved host bindings, all private services have no published ports, resource limits match the specification, Alloy shares Nginx networking, and the Prometheus retention flags are present.

- [ ] **Step 6: Add the isolated production smoke test**

Add these functions before the mode dispatch in `scripts/check_docker_deploy.sh`:

```bash
query_monitoring_service() {
  local network="$1"
  shift
  docker run --rm --network "$network" curlimages/curl:8.14.1 "$@"
}

smoke_production() (
  set -euo pipefail

  if command -v ss >/dev/null 2>&1 && ss -H -ltn 'sport = :80' | grep -q .; then
    printf 'Port 80 is already in use; production smoke test cannot start.\n' >&2
    exit 1
  fi

  project="haiun-check-production-$$"
  temp_dir="$(mktemp -d)"
  config_dir="$temp_dir/config"
  secret_file="$temp_dir/grafana_admin_password.txt"
  grafana_password="haiun-check-grafana-password"
  edge_network="${project}-edge"
  monitoring_network="${project}-monitoring"
  mkdir -p "$config_dir"
  printf '%s\n' "$grafana_password" >"$secret_file"
  chmod 600 "$secret_file"

  export HAIUN_IMAGE=haiun-check:app
  export HAIUN_DATA_VOLUME="${project}-data"
  export HAIUN_CONFIG_DIR="$config_dir"
  export HAIUN_TRUSTED_PROXIES_FILE="$root/deploy/nginx/trusted-proxies.default.conf"
  export HAIUN_LOKI_VOLUME="${project}-loki"
  export HAIUN_PROMETHEUS_VOLUME="${project}-prometheus"
  export HAIUN_GRAFANA_VOLUME="${project}-grafana"
  export HAIUN_EDGE_NETWORK="$edge_network"
  export HAIUN_MONITORING_NETWORK="$monitoring_network"
  export GRAFANA_ADMIN_PASSWORD_FILE="$secret_file"

  cleanup() {
    docker compose -p "$project" -f compose.production.yml down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$temp_dir"
  }
  trap cleanup EXIT

  docker compose -p "$project" -f compose.production.yml up -d --no-build

  assert_memory() {
    local service="$1"
    local expected="$2"
    local container_id
    local actual
    container_id="$(docker compose -p "$project" -f compose.production.yml ps -q "$service")"
    actual="$(docker inspect --format '{{.HostConfig.Memory}}' "$container_id")"
    test "$actual" = "$expected"
  }

  assert_memory haiun 805306368
  assert_memory grafana 201326592
  assert_memory loki 201326592
  assert_memory prometheus 201326592
  assert_memory alloy 100663296
  assert_memory nginx 67108864

  nginx_id="$(docker compose -p "$project" -f compose.production.yml ps -q nginx)"
  grafana_id="$(docker compose -p "$project" -f compose.production.yml ps -q grafana)"
  docker inspect --format '{{json .HostConfig.PortBindings}}' "$nginx_id" | rg -q '"HostPort":"80"'
  docker inspect --format '{{json .HostConfig.PortBindings}}' "$grafana_id" | rg -q '"HostIp":"127.0.0.1","HostPort":"3000"'
  for private_service in haiun alloy loki prometheus; do
    container_id="$(docker compose -p "$project" -f compose.production.yml ps -q "$private_service")"
    if docker inspect --format '{{json .HostConfig.PortBindings}}' "$container_id" | rg -q 'HostPort'; then
      printf '%s unexpectedly publishes a host port.\n' "$private_service" >&2
      exit 1
    fi
  done

  curl --fail --silent --show-error --retry 60 --retry-delay 1 --retry-connrefused \
    http://127.0.0.1/api/health |
    python3 -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ok"'

  test "$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1/metrics)" = "404"

  curl --fail --silent --show-error \
    -H 'X-Forwarded-For: 203.0.113.42' \
    -H 'X-Forwarded-Proto: https' \
    -H 'Referer: https://example.com/private/path?oauth_token=must-not-log' \
    -H 'User-Agent: HaiunDeploymentCheck/1.0' \
    'http://127.0.0.1/api/health?oauth_token=must-not-log' >/dev/null

  prometheus_ready=0
  for _ in $(seq 1 60); do
    if query_monitoring_service "$monitoring_network" --fail --silent --get \
      --data-urlencode 'query=min(up{job=~"haiun|prometheus|loki|alloy"})' \
      http://prometheus:9090/api/v1/query |
      python3 -c '
import json, sys
payload = json.load(sys.stdin)
assert payload["status"] == "success"
assert payload["data"]["result"][0]["value"][1] == "1"
'; then
      prometheus_ready=1
      break
    fi
    sleep 1
  done
  test "$prometheus_ready" = "1"

  loki_ready=0
  for _ in $(seq 1 30); do
    response="$(query_monitoring_service "$monitoring_network" --fail --silent --get \
      --data-urlencode 'query={service="haiun", log_type="api_access"}' \
      --data-urlencode 'limit=100' \
      http://loki:3100/loki/api/v1/query_range || true)"
    if printf '%s' "$response" | rg -q '203\.0\.113\.42'; then
      printf '%s' "$response" | rg -q 'example\.com'
      if printf '%s' "$response" | rg -q 'must-not-log|private/path'; then
        printf 'Forbidden query or referrer detail reached Loki.\n' >&2
        exit 1
      fi
      loki_ready=1
      break
    fi
    sleep 1
  done
  test "$loki_ready" = "1"

  curl --fail --silent --show-error --retry 30 --retry-delay 1 --retry-connrefused \
    http://127.0.0.1:3000/api/health |
    python3 -c 'import json, sys; assert json.load(sys.stdin)["database"] == "ok"'

  dashboards_ready=0
  for _ in $(seq 1 30); do
    if curl --fail --silent --show-error \
      --user "admin:${grafana_password}" \
      'http://127.0.0.1:3000/api/search?query=Haiun' |
      python3 -c '
import json, sys
titles = {item["title"] for item in json.load(sys.stdin)}
assert {
    "Haiun API Overview",
    "Haiun Access Sources",
    "Haiun Backend Runtime",
}.issubset(titles)
'; then
      dashboards_ready=1
      break
    fi
    sleep 1
  done
  test "$dashboards_ready" = "1"
)
```

Change the `production)` mode to run both `check_production_config` and `smoke_production`. Make `all` run `check_production_config` and `smoke_production` after the static validators.

- [ ] **Step 7: Run the full production smoke test**

Run:

```bash
scripts/check_docker_deploy.sh production
```

Expected:

- `http://127.0.0.1/api/health` returns healthy through Nginx on port 80.
- Public `/metrics` returns 404.
- Prometheus reports Haiun, Prometheus, Loki, and Alloy scrape health equal to 1.
- Loki contains client IP `203.0.113.42`, referrer host `example.com`, and no query token or referrer path.
- Grafana reports a healthy database and lists all three provisioned dashboards.
- Runtime Docker inspection confirms the six memory limits and only the approved Nginx and Grafana host bindings.
- Cleanup removes the isolated containers, networks, test volumes, empty config directory, and temporary Grafana password.

- [ ] **Step 8: Commit only the production integration files**

Run:

```bash
git add compose.production.yml .gitignore scripts/check_docker_deploy.sh
git commit --only compose.production.yml .gitignore scripts/check_docker_deploy.sh \
  -m "feat: add monitored production deployment"
```

---

### Task 7: Document Operations and Run Full Verification

**Files:**
- Create: `.env.docker.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: all Compose variables and operator workflows from Tasks 2–6.
- Produces: copyable start, stop, upgrade, trusted-proxy, Grafana tunnel, backup, restore, swap, and diagnostic commands.
- Produces: final verification evidence for backend, frontend, shell, Docker configuration, simple mode, production monitoring, and secret exclusion.

- [ ] **Step 1: Add the non-secret Docker environment example**

Create `.env.docker.example`:

```dotenv
HAIUN_IMAGE=haiun:local
HAIUN_SIMPLE_PORT=8765
HAIUN_METRICS_ENABLED=false
HAIUN_DATA_VOLUME=haiun-data
HAIUN_CONFIG_DIR=./config
HAIUN_TRUSTED_PROXIES_FILE=./deploy/nginx/trusted-proxies.default.conf
HAIUN_LOKI_VOLUME=haiun-loki
HAIUN_PROMETHEUS_VOLUME=haiun-prometheus
HAIUN_GRAFANA_VOLUME=haiun-grafana
HAIUN_EDGE_NETWORK=haiun-edge
HAIUN_MONITORING_NETWORK=haiun-monitoring
GRAFANA_ADMIN_PASSWORD_FILE=./secrets/grafana_admin_password.txt
```

This file contains paths and resource names only. Do not put a password or Mahjong Soul credential in it.

- [ ] **Step 2: Add Docker prerequisites and simple-mode documentation**

Add a `## Docker` section to `README.md` after the existing conventional Linux instructions. Include:

````markdown
### Prerequisites

Install Docker Engine 28 or newer and Docker Compose 2.40 or newer. Copy the
non-secret environment example only when you need to override volume names or
paths:

```bash
cp .env.docker.example .env
```

Keep `config/config.toml` local with mode `0600`. Docker mounts the `config/`
directory read-only; it never copies the real file into the image.

### Simple mode

```bash
docker compose -f compose.simple.yml up -d --build
docker compose -f compose.simple.yml ps
curl http://127.0.0.1:8765/api/health
```

Stop the service without deleting data:

```bash
docker compose -f compose.simple.yml down
```
````

- [ ] **Step 3: Add production setup and trusted-proxy documentation**

Continue the Docker section with these exact operational requirements:

````markdown
### Production mode

Production Nginx binds host port 80 and expects an existing TLS proxy or load
balancer to forward HTTP to it. Restrict server port 80 so only that proxy can
connect. The stack itself does not issue certificates or terminate public TLS.

Create a Grafana password file without printing it:

```bash
install -d -m 0700 secrets
umask 077
openssl rand -base64 32 > secrets/grafana_admin_password.txt
```

If the TLS proxy does not connect from loopback or an RFC1918 address, copy the
default Nginx include and replace its networks with the proxy's documented
source networks:

```bash
cp deploy/nginx/trusted-proxies.default.conf config/trusted-proxies.conf
```

Set this non-secret path in `.env`:

```dotenv
HAIUN_TRUSTED_PROXIES_FILE=./config/trusted-proxies.conf
```

Start production:

```bash
docker compose -f compose.production.yml up -d --build
docker compose -f compose.production.yml ps
curl http://127.0.0.1/api/health
```

Only Nginx is public. Grafana binds to loopback and is reached through SSH:

```bash
ssh -L 3000:127.0.0.1:3000 user@server
```

Then open `http://127.0.0.1:3000` locally and sign in as `admin` with the
password stored in `secrets/grafana_admin_password.txt`.
````

Explicitly state that the trusted-proxy file is security-sensitive configuration even though it contains no credential: trusting `0.0.0.0/0` would allow direct clients to spoof source IPs and must not be documented as an example.

- [ ] **Step 4: Add dashboard, health, and resource documentation**

Document the three dashboards and these commands:

```bash
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=200 nginx haiun alloy loki prometheus grafana
docker stats --no-stream
docker compose -f compose.production.yml exec prometheus \
  wget -qO- http://127.0.0.1:9090/-/ready
docker compose -f compose.production.yml exec grafana \
  wget -qO- http://127.0.0.1:3000/api/health
```

Describe the dashboard contents accurately:

- API Overview: rate, status/error distribution, p50/p95/p99 latency, in-progress requests, busiest normalized routes.
- Access Sources: client IPs, referrer hosts, user-agents, recent requests, slow requests, failed requests.
- Backend Runtime: Python CPU, resident memory, garbage collection, uptime, Haiun scrape health, and monitoring-service scrape health.

State that logs and metrics retain 30 days, Grafana is localhost-only, no geolocation is performed, and host-wide metrics are not collected by default.

- [ ] **Step 5: Add backup, restore, upgrade, and swap documentation**

Document a stopped-service backup:

```bash
docker compose -f compose.production.yml down
docker run --rm \
  -v haiun-data:/data:ro \
  -v "$PWD":/backup \
  alpine:3.22 \
  tar -czf /backup/haiun-data.tar.gz -C /data .
```

Document restore into an empty named volume:

```bash
docker volume create haiun-data
docker run --rm \
  -v haiun-data:/data \
  -v "$PWD":/backup:ro \
  alpine:3.22 \
  tar -xzf /backup/haiun-data.tar.gz -C /data
```

Document upgrade:

```bash
git pull --ff-only
docker compose -f compose.production.yml build --pull
docker compose -f compose.production.yml up -d
```

Document 2 GiB host guidance:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
swapon --show
```

State that swap is emergency protection, not a substitute for CPU or RAM, and recommend at least 4 GiB RAM if analysis concurrency, traffic, dashboard use, or retained data grows materially. Tell operators to add the swapfile to `/etc/fstab` using their distribution's documented procedure rather than prescribing an unreviewed line automatically.

- [ ] **Step 6: Add Docker verification commands to the README test section**

Append:

```bash
docker compose -f compose.simple.yml config
GRAFANA_ADMIN_PASSWORD_FILE=/dev/null docker compose -f compose.production.yml config
scripts/check_docker_deploy.sh all
```

Explain that the production smoke test requires host port 80 to be free and uses isolated temporary configuration, secret, network, and volume names.

- [ ] **Step 7: Run documentation and secret scans**

Run:

```bash
git diff --check -- README.md .env.docker.example
if rg -n -i \
  'replace-with-a-real|oauth_token=.*[^<]|browser_session=.*[^<]|grafana_admin_password=.*[^<]' \
  README.md .env.docker.example; then
  exit 1
fi
```

Expected: no whitespace errors and no embedded real-looking secret values.

- [ ] **Step 8: Run the complete backend and frontend verification**

Run:

```bash
nix develop -c .venv/bin/python -m pytest backend/tests -v
nix develop -c npm --prefix frontend test
nix develop -c npm --prefix frontend run build
nix develop -c npm --prefix frontend run e2e
```

Expected: all backend, frontend, build, and end-to-end checks pass. If end-to-end execution is blocked by a missing system browser dependency, preserve the complete error output and fix the documented environment rather than silently skipping the check.

- [ ] **Step 9: Run shell and Docker verification**

Run:

```bash
bash -n scripts/dev.sh scripts/start.sh scripts/check_docker_deploy.sh
shellcheck scripts/dev.sh scripts/start.sh scripts/check_docker_deploy.sh
scripts/check_docker_deploy.sh all
```

Expected: shell syntax and ShellCheck pass; the application image builds; both Compose files validate; Nginx, Alloy, Loki, Prometheus, and Grafana configs validate; simple mode responds on the isolated port; production responds on port 80; Prometheus and Loki contain the generated test data; Grafana lists all dashboards.

- [ ] **Step 10: Confirm repository cleanliness boundaries and commit docs**

Run:

```bash
git diff --check
git status --short
```

Expected: only the task's intended README and environment example changes are unstaged for this task, plus the user's pre-existing staged `AGENTS.md` change.

Commit only the documentation files:

```bash
git add README.md .env.docker.example
git commit --only README.md .env.docker.example \
  -m "docs: add Docker deployment guide"
```

- [ ] **Step 11: Request a final code review**

Invoke `superpowers:requesting-code-review` with the approved design, this implementation plan, the commit range beginning after the design commit `ba3f51d`, and the full verification output. Address any correctness or security findings through `superpowers:receiving-code-review`, rerun the affected checks, and create focused follow-up commits with `git commit --only`.

- [ ] **Step 12: Perform completion verification**

Invoke `superpowers:verification-before-completion`. Rerun any command whose output is no longer current after review fixes. Report Docker image build evidence, both smoke-test results, port exposure, memory limits, retention, dashboard provisioning, and the full repository test results before claiming completion.

---

## Expected Commit Sequence

1. `feat: add internal API metrics`
2. `feat: add simple Docker deployment`
3. `feat: add production Nginx edge`
4. `feat: add production telemetry storage`
5. `feat: provision monitoring dashboards`
6. `feat: add monitored production deployment`
7. `docs: add Docker deployment guide`

Each commit must exclude the user's staged `AGENTS.md` change.

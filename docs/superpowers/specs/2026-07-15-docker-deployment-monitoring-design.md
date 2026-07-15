# Docker Deployment and Monitoring Design

## Goal

Add two Docker deployment modes for 牌运 Haiun:

- A simple mode that builds and runs the application as one container.
- A production mode that places Nginx in front of the application and provides resource-conscious API traffic and backend monitoring for a server with 2 CPU cores and 2 GiB of RAM.

Production Nginx listens on host port 80 and receives HTTP from an existing TLS proxy or load balancer. The Docker stack does not obtain certificates or terminate public TLS. Grafana listens only on `127.0.0.1:3000`. Monitoring data is retained for 30 days and does not include IP geolocation.

## Constraints

- Preserve the existing FastAPI application, Vite frontend, SQLite storage, environment settings, and local TOML configuration.
- Build one reusable application image for both deployment modes.
- Never copy `config/config.toml`, the data directory, Mahjong Soul credentials, administrator credentials, OAuth tokens, verification codes, or browser sessions into an image or monitoring record.
- Do not log request bodies, query strings, cookies, authorization headers, or raw referrer query parameters.
- Keep the production application usable if any monitoring component fails.
- Keep monitoring memory usage low enough for a 2 GiB host, with documented swap and upgrade guidance.
- Preserve unrelated in-progress public-access work in the repository.

## Approaches Considered

### Metrics-only monitoring

Nginx, Prometheus, and Grafana would provide request totals and connection data with a small operational footprint. This cannot adequately answer which client IPs, referrer sources, user agents, or individual request records produced the traffic.

### GoAccess access-log monitoring

Nginx and GoAccess would provide a lightweight traffic dashboard with useful source information. It would not provide strong FastAPI latency, error, process memory, CPU, garbage collection, or scrape-health monitoring.

### Selected: memory-optimized Grafana stack

Use Nginx, Grafana Alloy, Loki, Prometheus, and Grafana around one Haiun container. Nginx access records provide traffic-source detail, while a focused FastAPI Prometheus integration provides normalized endpoint and process metrics. Host-wide exporters, cAdvisor, Alertmanager, and geolocation are excluded by default to fit the target server.

## Application Image

Create one multi-stage `Dockerfile`:

1. A Node 22 build stage installs the locked frontend dependencies and builds `frontend/dist`.
2. A Python 3.13 slim runtime stage installs the locked Python project dependencies.
3. The runtime image copies the backend source, Alembic assets needed by the repository, and the built frontend into a repository-shaped `/app` tree so the existing static-file path resolution continues to work.
4. The image sets `PYTHONPATH=/app/backend`, `HAIUN_DATA_DIR=/data`, and `HAIUN_CONFIG=/app/config/config.toml`.
5. The process runs as a dedicated non-root user and starts one Uvicorn worker.

The `.dockerignore` file excludes Git metadata, virtual environments, node modules, frontend build output, tests not required at runtime, local data, real configuration, monitoring volumes, and secret files. The real configuration is mounted at runtime through a read-only `/app/config` directory.

## Simple Deployment Mode

`compose.simple.yml` contains one `haiun` service:

- Build the shared application image.
- Publish `8765:8765` by default.
- Mount the shared named `haiun-data` volume at `/data`.
- Mount `./config` read-only at `/app/config` so a missing `config.toml` preserves the application's existing locked/unconfigured behavior.
- Run one Uvicorn worker without proxy-header trust.
- Check `GET /api/health` and restart with `unless-stopped`.
- Leave Prometheus instrumentation disabled unless the operator explicitly enables it.

The operator starts the mode with:

```bash
docker compose -f compose.simple.yml up -d --build
```

This mode is intended for local, LAN, or otherwise protected use. It does not add Nginx, TLS, or monitoring services.

## Production Deployment Mode

`compose.production.yml` is standalone so it cannot inherit or accidentally retain the simple mode's published backend port. It contains:

- `nginx`: the only public service, publishing exactly `80:80`.
- `haiun`: the application on a private network with no published host port.
- `alloy`: an internal structured-log receiver and Loki client.
- `loki`: internal access-log storage.
- `prometheus`: internal metrics collection and storage.
- `grafana`: provisioned dashboards and data sources, publishing only `127.0.0.1:3000:3000`.

The services use private application and monitoring networks. Prometheus reaches Haiun directly for scraping. Nginx reaches Haiun for proxying and Alloy for access-log delivery. No Prometheus, Loki, Alloy, or Haiun port is published on the host.

The operator starts the mode with:

```bash
docker compose -f compose.production.yml up -d --build
```

## Nginx Proxy and Access Logging

Nginx proxies frontend and API traffic to the internal Haiun service. It preserves the upstream TLS proxy's host, client-forwarding, and `X-Forwarded-Proto` information. The production Uvicorn command accepts proxy headers because the application is reachable only through private Docker networking.

Trusted real-client forwarding is controlled by a mounted Nginx include file. The repository provides a safe default for loopback and private proxy networks, and the deployment guide explains how to provide a different file for the actual TLS proxy addresses. The server firewall must restrict host port 80 to the existing TLS proxy or load balancer wherever the infrastructure supports that restriction.

Nginx applies the existing 32 MiB upload limit and a conservative per-client API request limit of 10 requests per second with a burst of 20, returning HTTP 429 when exceeded. Health and static assets do not consume the API rate-limit zone.

Only `/api/` access records are sent to Alloy. Nginx formats each record as JSON within an internal syslog message containing:

- Timestamp and Nginx request ID
- Resolved client IP, immediate proxy IP, and forwarded chain
- HTTP method and URI path without query parameters
- HTTP status, response bytes, total request time, and upstream response time
- Referrer host with its path, query, and fragment removed
- User-agent

Nginx never logs request bodies, query strings, cookies, authorization headers, configured credentials, or session tokens. Alloy receives these records over the private Docker network and sends them to Loki. Client IP, forwarding data, referrer host, and user-agent remain parsed fields rather than Loki labels. Stable low-cardinality labels identify only the service, environment, and log type.

The log path is non-blocking from the application's perspective. If Alloy or Loki is unavailable, Haiun and Nginx continue serving requests; access records produced during the outage may be lost rather than buffering without bound on the 2 GiB host.

## FastAPI Metrics

Add a small in-repository Prometheus middleware using `prometheus-client` rather than a broad automatic instrumentation package. A new `HAIUN_METRICS_ENABLED` setting defaults to false. When enabled by production Compose, Haiun exposes an internal, schema-hidden `/metrics` endpoint that Nginx does not proxy publicly.

The middleware observes only `/api/` requests and exports:

- `haiun_http_requests_total` by method, normalized route template, and status code.
- `haiun_http_request_duration_seconds` by method and normalized route template.
- `haiun_http_requests_in_progress` by method.
- Standard Python process CPU, resident memory, garbage collection, and process-start metrics.

Route labels come from the matched FastAPI route template, such as `/api/results/{submission_id}`, rather than raw paths containing UUIDs, player identifiers, or other unbounded values. Unmatched routes use one fixed label. Metrics never contain query parameters, request bodies, client IPs, credentials, cookies, tokens, or exception messages.

Prometheus scrapes Haiun every 30 seconds. It retains metrics for 30 days with a 512 MiB storage-size cap. Loki retains logs for 720 hours and compacts expired data. Only API access is ingested, reducing both disk and memory pressure.

## Grafana Provisioning

Grafana starts with Prometheus and Loki data sources and three version-controlled dashboards already provisioned:

### API overview

- Requests per second
- Error rate and status distribution
- p50, p95, and p99 request latency
- Current in-progress requests
- Busiest normalized API routes

### Access sources

- Top resolved client IPs
- Top referrer hosts
- Top user-agents
- Recent API request records
- Slow and failed request tables

### Backend runtime

- Python process CPU and resident memory
- Garbage collection activity
- Process uptime
- Prometheus scrape health
- Monitoring data-source health

Grafana has no public binding. The deployment guide uses an SSH tunnel:

```bash
ssh -L 3000:127.0.0.1:3000 user@server
```

The Grafana administrator password comes from a git-ignored file-backed Compose secret through `GF_SECURITY_ADMIN_PASSWORD__FILE`. No default `admin/admin` credential is accepted by the production setup.

## Resource Envelope

Production Compose starts with these hard memory limits:

| Service | Memory limit |
| --- | ---: |
| Haiun | 768 MiB |
| Grafana | 192 MiB |
| Loki | 192 MiB |
| Prometheus | 192 MiB |
| Alloy | 96 MiB |
| Nginx | 64 MiB |

The total container limit is approximately 1.5 GiB, leaving roughly 500 MiB for Linux, Docker, filesystem cache, and short-lived overhead. Haiun uses one worker so multiple Python worker processes cannot duplicate caches and memory. Prometheus uses a 30-second scrape interval, and no optional Grafana plugins are installed.

The deployment guide recommends 1–2 GiB of swap as emergency protection and explains that swap prevents abrupt out-of-memory termination but does not add CPU capacity. It recommends upgrading to at least 4 GiB RAM if analysis concurrency, traffic, dashboard use, or retained data grows materially.

Host-wide exporters and cAdvisor are deliberately excluded from the default production file. They may be documented as a future optional profile, but they are not part of this implementation.

## Health, Startup, and Failure Isolation

Every service uses `restart: unless-stopped` and an appropriate health check:

- Haiun: `/api/health`
- Nginx: an internal health location plus an upstream request check
- Prometheus: `/-/ready`
- Loki: `/ready`
- Grafana: `/api/health`
- Alloy: its configured health endpoint

Nginx waits for a healthy Haiun service before becoming the normal entry point. Monitoring services do not gate Haiun startup. Grafana may initially show a data source as unavailable while Loki or Prometheus restarts, but this does not affect public traffic.

The application continues using its existing SQLite initialization behavior. Both modes share the explicitly named `haiun-data` volume so switching modes does not create a second database accidentally. Monitoring data uses separate named volumes. The deployment guide requires a Haiun data backup before upgrades and documents export, restore, and volume inspection commands.

## Operator Configuration

Repository configuration additions include:

- An example environment file containing only non-secret tuning values.
- A git-ignored `secrets/` path for the Grafana password file.
- A default trusted-proxy include covering safe local/private networks.
- Documentation for overriding the trusted-proxy file with the actual upstream proxy networks.

The deployment guide covers:

- Docker Engine and Compose prerequisites.
- Preparing `config/config.toml` with mode `0600` without displaying or copying its contents.
- Creating the Grafana secret file.
- Starting, stopping, rebuilding, and upgrading each mode.
- Firewalling production port 80 to the existing TLS proxy.
- Opening Grafana through an SSH tunnel.
- Checking health, resource use, logs, Prometheus targets, Loki ingestion, and dashboards.
- Backing up and restoring the Haiun named volume.
- Adding swap and adjusting resource limits.

## Testing and Verification

Backend tests cover:

- Metrics disabled by default.
- Metrics enabled through settings.
- The internal metrics endpoint omitted from OpenAPI.
- Only `/api/` requests instrumented.
- Normalized route-template labels for dynamic URLs.
- No query values, raw identifiers, credentials, cookies, tokens, or exception text in metrics.

Deployment checks cover:

- Building the multi-stage application image.
- `docker compose config` for both standalone Compose files.
- Nginx configuration validation.
- Alloy, Loki, Prometheus, and Grafana configuration validation where their images provide validation commands.
- Simple-mode smoke testing through port 8765.
- Production smoke testing through Nginx on port 80.
- Confirmation that Haiun and monitoring service ports are not published in production.
- Confirmation that Grafana binds only to `127.0.0.1:3000`.
- Generated API requests appearing in Prometheus and Loki.
- Provisioned Grafana data sources and dashboards loading successfully.
- Configured container memory limits matching the design.

The existing backend test suite, frontend test suite, frontend production build, end-to-end tests when the environment supports them, and shell checks continue to run before completion.

## Expected File Scope

- `Dockerfile`
- `.dockerignore`
- `compose.simple.yml`
- `compose.production.yml`
- Docker/runtime helper script if needed for a clean non-root startup
- `deploy/nginx/` configuration and trusted-proxy defaults
- `deploy/alloy/` configuration
- `deploy/loki/` configuration
- `deploy/prometheus/` configuration
- `deploy/grafana/` provisioning and dashboard JSON
- Backend settings, metrics middleware, dependency metadata, and focused tests
- `.gitignore` additions for Docker secret material
- `README.md` Docker deployment and operations documentation

No frontend behavior, Mahjong analysis logic, scoring behavior, three-player rules, translation resources, authentication secrets, or existing API authorization rules change as part of this work.

## Out of Scope

- TLS certificate issuance or termination inside the Docker stack
- IP geolocation
- Public Grafana exposure
- Alertmanager or notification delivery
- cAdvisor, node exporter, or other host-wide exporters by default
- Kubernetes, Docker Swarm, or multi-host orchestration
- Horizontal scaling or multiple Uvicorn workers
- External databases or object storage
- A new database migration policy beyond the application's existing behavior

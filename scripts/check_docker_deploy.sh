#!/usr/bin/env bash
set -euo pipefail

root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

mode="${1:-all}"

check_simple_config() {
  docker build \
    --build-arg PYPI_INDEX_URL="${HAIUN_PYPI_INDEX_URL:-https://pypi.org/simple}" \
    --tag haiun-check:app .
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
  # shellcheck disable=SC2329  # Invoked indirectly by the EXIT trap.
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
    --retry-all-errors \
    "http://127.0.0.1:${port}/api/health" |
    python3 -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ok"'
)

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

check_grafana_config() {
  python3 - <<'PY'
import json
from pathlib import Path

dashboard_dir = Path("deploy/grafana/dashboards")
expected_dashboards = {
    "haiun-api-overview.json": {
        "uid": "haiun-api-overview",
        "title": "Haiun API Overview",
        "datasource": {"type": "prometheus", "uid": "prometheus"},
        "panels": {
            "Requests per second": [
                "sum(rate(haiun_http_requests_total[5m]))",
            ],
            "Server error rate": [
                '(sum(increase(haiun_http_requests_total{status=~"5.."}[5m])) '
                "or vector(0)) / clamp_min((sum(increase("
                "haiun_http_requests_total[5m])) or vector(0)), 1)",
            ],
            "API latency": [
                "histogram_quantile(0.50, sum by (le) (rate("
                "haiun_http_request_duration_seconds_bucket[5m])))",
                "histogram_quantile(0.95, sum by (le) (rate("
                "haiun_http_request_duration_seconds_bucket[5m])))",
                "histogram_quantile(0.99, sum by (le) (rate("
                "haiun_http_request_duration_seconds_bucket[5m])))",
            ],
            "Requests in progress": [
                "sum(haiun_http_requests_in_progress)",
            ],
            "Busiest normalized routes": [
                "topk(10, sum by (method, route) (rate("
                "haiun_http_requests_total[5m])))",
            ],
        },
    },
    "haiun-access-sources.json": {
        "uid": "haiun-access-sources",
        "title": "Haiun Access Sources",
        "datasource": {"type": "loki", "uid": "loki"},
        "panels": {
            "Top client IPs": [
                "topk(10, sum by (client_ip) (count_over_time("
                '{service="haiun", log_type="api_access"} | json | '
                '__error__="" [5m])))',
            ],
            "Top referrer hosts": [
                "topk(10, sum by (referrer_host) (count_over_time("
                '{service="haiun", log_type="api_access"} | json | '
                '__error__="" | referrer_host != "" [5m])))',
            ],
            "Top user-agents": [
                "topk(10, sum by (user_agent) (count_over_time("
                '{service="haiun", log_type="api_access"} | json | '
                '__error__="" [5m])))',
            ],
            "Recent API requests": [
                '{service="haiun", log_type="api_access"} | json',
            ],
            "Slow or failed requests": [
                '{service="haiun", log_type="api_access"} | json | '
                '__error__="" | request_time > 1',
                '{service="haiun", log_type="api_access"} | json | '
                '__error__="" | status >= 500',
            ],
        },
    },
    "haiun-backend-runtime.json": {
        "uid": "haiun-backend-runtime",
        "title": "Haiun Backend Runtime",
        "datasource": {"type": "prometheus", "uid": "prometheus"},
        "panels": {
            "Python process CPU": [
                'rate(process_cpu_seconds_total{job="haiun"}[5m])',
            ],
            "Python process memory": [
                'process_resident_memory_bytes{job="haiun"}',
            ],
            "Garbage collections": [
                "sum by (generation) (rate("
                'python_gc_collections_total{job="haiun"}[5m]))',
            ],
            "Process uptime": [
                'time() - process_start_time_seconds{job="haiun"}',
            ],
            "Haiun scrape health": [
                'up{job="haiun"}',
            ],
            "Monitoring service scrape health": [
                'up{job=~"prometheus|loki|alloy"}',
            ],
        },
    },
}

actual_files = {path.name for path in dashboard_dir.glob("*.json")}
assert actual_files == set(expected_dashboards), actual_files

for filename, expected in expected_dashboards.items():
    dashboard = json.loads((dashboard_dir / filename).read_text(encoding="utf-8"))
    assert dashboard["uid"] == expected["uid"]
    assert dashboard["title"] == expected["title"]
    assert dashboard["refresh"] == "30s"
    assert dashboard["panels"]

    panel_ids = [panel["id"] for panel in dashboard["panels"]]
    assert all(isinstance(panel_id, int) and panel_id > 0 for panel_id in panel_ids), (
        filename,
        panel_ids,
    )
    assert len(panel_ids) == len(set(panel_ids)), (filename, panel_ids)

    panel_titles = [panel["title"] for panel in dashboard["panels"]]
    assert len(panel_titles) == len(set(panel_titles)), (filename, panel_titles)
    assert set(panel_titles) == set(expected["panels"]), (filename, panel_titles)

    for panel in dashboard["panels"]:
        assert panel["datasource"] == expected["datasource"], (
            filename,
            panel["title"],
            panel["datasource"],
        )
        expressions = [target["expr"] for target in panel["targets"]]
        assert expressions == expected["panels"][panel["title"]], (
            filename,
            panel["title"],
            expressions,
        )

    if filename == "haiun-api-overview.json":
        error_panel = next(
            panel
            for panel in dashboard["panels"]
            if panel["title"] == "Server error rate"
        )
        assert error_panel["fieldConfig"]["defaults"]["unit"] == "percentunit"

    dashboard_text = json.dumps(dashboard).lower()
    for forbidden in (
        "oauth_token",
        "haiun_admin_session",
        "request_body",
        "authorization",
    ):
        assert forbidden not in dashboard_text, (filename, forbidden)


def parse_scalar(value):
    if value == "true":
        return True
    if value == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def parse_root_scalar(path, key):
    prefix = f"{key}:"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return parse_scalar(line.partition(":")[2].strip())
    raise AssertionError(f"missing {key} in {path}")


def parse_records(path, section):
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"{section}:") + 1
    records = []
    current = None
    nested_key = None

    for line in lines[start:]:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            break
        content = line.strip()
        record_start = False

        if indent == 2:
            if not content.startswith("- "):
                raise AssertionError(
                    f"invalid {section} record continuation in {path}: {line}"
                )
            current = {}
            records.append(current)
            nested_key = None
            content = content[2:]
            record_start = True
        elif current is None:
            raise AssertionError(f"invalid {section} record in {path}: {line}")

        key, separator, value = content.partition(":")
        assert separator, (path, section, line)
        value = value.strip()

        if record_start or indent == 4:
            if value:
                current[key] = parse_scalar(value)
                nested_key = None
            else:
                current[key] = {}
                nested_key = key
        elif indent == 6 and nested_key is not None:
            current[nested_key][key] = parse_scalar(value)
        else:
            raise AssertionError(f"unsupported {section} structure in {path}: {line}")

    return records

datasource_path = Path("deploy/grafana/provisioning/datasources/haiun.yml")
assert parse_root_scalar(datasource_path, "apiVersion") == 1
assert parse_records(datasource_path, "deleteDatasources") == [
    {"name": "Prometheus", "orgId": 1},
    {"name": "Loki", "orgId": 1},
]
datasources = parse_records(datasource_path, "datasources")
assert datasources == [
    {
        "name": "Prometheus",
        "uid": "prometheus",
        "type": "prometheus",
        "access": "proxy",
        "url": "http://prometheus:9090",
        "isDefault": True,
        "editable": False,
        "jsonData": {"timeInterval": "30s"},
    },
    {
        "name": "Loki",
        "uid": "loki",
        "type": "loki",
        "access": "proxy",
        "url": "http://loki:3100",
        "editable": False,
    },
]

provider_path = Path("deploy/grafana/provisioning/dashboards/haiun.yml")
assert parse_root_scalar(provider_path, "apiVersion") == 1
assert parse_records(provider_path, "providers") == [
    {
        "name": "Haiun",
        "orgId": 1,
        "folder": "Haiun",
        "type": "file",
        "disableDeletion": True,
        "allowUiUpdates": False,
        "updateIntervalSeconds": 30,
        "options": {"path": "/var/lib/grafana/dashboards"},
    },
]
PY
}

case "$mode" in
  simple)
    check_simple_config
    smoke_simple
    ;;
  nginx)
    check_nginx_config
    ;;
  telemetry)
    check_telemetry_config
    ;;
  grafana)
    check_grafana_config
    ;;
  all)
    check_simple_config
    smoke_simple
    check_nginx_config
    check_telemetry_config
    check_grafana_config
    ;;
  *)
    printf 'Usage: %s [simple|nginx|telemetry|grafana|all]\n' "$0" >&2
    exit 2
    ;;
esac

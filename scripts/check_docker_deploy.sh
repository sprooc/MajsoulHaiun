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

smoke_exit_status() {
  local original_status="$1"
  local cleanup_status="$2"

  if test "$original_status" -ne 0; then
    return "$original_status"
  fi
  return "$cleanup_status"
}

check_smoke_exit_status() {
  local actual_status

  if smoke_exit_status 0 1; then
    actual_status=0
  else
    actual_status="$?"
  fi
  test "$actual_status" = "1"

  if smoke_exit_status 7 1; then
    actual_status=0
  else
    actual_status="$?"
  fi
  test "$actual_status" = "7"
}

check_production_config() {
  check_smoke_exit_status
  check_precompose_cleanup
  docker build \
    --build-arg PYPI_INDEX_URL="${HAIUN_PYPI_INDEX_URL:-https://pypi.org/simple}" \
    --tag haiun-check:app .
  # shellcheck disable=SC2016  # Python checks literal Compose shell variables.
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
import json, os, sys
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
    assert int(services[service]["mem_limit"]) == expected

assert services["alloy"]["network_mode"] == "service:nginx"
assert services["haiun"]["environment"]["HAIUN_METRICS_ENABLED"] == "true"
assert services["grafana"]["environment"]["GF_SECURITY_ADMIN_PASSWORD__FILE"] == "/run/secrets/grafana_admin_password"
assert set(services["grafana"]["networks"]) == {"edge", "monitoring"}
grafana_entrypoint = " ".join(services["grafana"]["entrypoint"])
assert services["grafana"]["user"] == "0"
assert services["grafana"]["tmpfs"] == [
    "/run/haiun-secrets:mode=0750,uid=0,gid=0,noexec,nosuid,nodev"
]
assert "cp -- \"$${GF_SECURITY_ADMIN_PASSWORD__FILE}\" \"$${secret_copy}\"" in grafana_entrypoint
assert "chown 472:0 \"$${secret_copy}\"" in grafana_entrypoint
assert "chmod 0400 \"$${secret_copy}\"" in grafana_entrypoint
assert (
    "GF_SECURITY_ADMIN_PASSWORD=\"\\$$__file{$${secret_copy}}\""
) in grafana_entrypoint
assert "unset GF_SECURITY_ADMIN_PASSWORD__FILE" in grafana_entrypoint
assert (
    "su -s /bin/bash grafana -c " + chr(39) + "exec /run.sh" + chr(39)
) in grafana_entrypoint
assert services["grafana"]["secrets"] == [
    {
        "source": "grafana_admin_password",
        "target": "/run/secrets/grafana_admin_password",
    }
]
assert config["secrets"]["grafana_admin_password"]["file"] == "/dev/null"
assert services["haiun"]["build"]["args"]["PYPI_INDEX_URL"] == os.environ.get(
    "HAIUN_PYPI_INDEX_URL", "https://pypi.org/simple"
)
prometheus_command = " ".join(services["prometheus"]["command"])
assert "--storage.tsdb.retention.time=30d" in prometheus_command
assert "--storage.tsdb.retention.size=512MB" in prometheus_command

assert not services["haiun"].get("depends_on")
assert services["nginx"]["depends_on"] == {
    "haiun": {"condition": "service_healthy", "required": True}
}
'
}

query_monitoring_service() {
  local network="$1"
  shift
  docker run --rm --network "$network" curlimages/curl:8.14.1 "$@"
}

assert_host_port_available() {
  local port="$1"
  local docker_owners
  local listeners

  listeners=""
  if command -v ss >/dev/null 2>&1; then
    listeners="$(ss -H -ltnp "sport = :$port" 2>/dev/null || true)"
  fi
  docker_owners="$(
    docker ps --filter "publish=$port" \
      --format 'container={{.ID}} name={{.Names}} ports={{.Ports}}'
  )"

  if test -n "$listeners" || test -n "$docker_owners"; then
    printf 'Port %s is already in use; production smoke test cannot start.\n' "$port" >&2
    if test -n "$listeners"; then
      printf 'Socket state: %s\n' "$listeners" >&2
    fi
    if test -n "$docker_owners"; then
      printf 'Docker owner: %s\n' "$docker_owners" >&2
    fi
    return 1
  fi
}

smoke_production() (
  set -euo pipefail
  umask 077

  # shellcheck disable=SC2329  # Invoked by the EXIT trap handler.
  cleanup_production_smoke() {
    local artifact
    local cleanup_failed=0

    if test -n "$credential_probe_pid" && kill -0 "$credential_probe_pid" 2>/dev/null; then
      kill "$credential_probe_pid" >/dev/null 2>&1 || true
      wait "$credential_probe_pid" >/dev/null 2>&1 || true
    fi

    if test "$compose_started" = "1"; then
      if ! docker compose -p "$production_project" -f compose.production.yml \
        down -v --remove-orphans >/dev/null 2>&1; then
        printf 'Failed to stop the isolated production stack.\n' >&2
        cleanup_failed=1
      fi
    fi

    if docker ps -a --filter "label=com.docker.compose.project=$production_project" \
      --format '{{.ID}}' | grep -q .; then
      printf 'Isolated production containers remain after cleanup.\n' >&2
      cleanup_failed=1
    fi
    for artifact in "$edge_network" "$monitoring_network"; do
      if docker network inspect "$artifact" >/dev/null 2>&1; then
        printf 'Isolated network remains after cleanup: %s\n' "$artifact" >&2
        cleanup_failed=1
      fi
    done
    for artifact in \
      "$data_volume" \
      "$loki_volume" \
      "$prometheus_volume" \
      "$grafana_volume"; do
      if docker volume inspect "$artifact" >/dev/null 2>&1; then
        printf 'Isolated volume remains after cleanup: %s\n' "$artifact" >&2
        cleanup_failed=1
      fi
    done

    if test -n "$temp_dir"; then
      rm -rf "$temp_dir"
    fi
    if { test -n "$temp_dir" && test -e "$temp_dir"; } ||
      { test -n "$production_config_dir" && test -e "$production_config_dir"; } ||
      { test -n "$secret_file" && test -e "$secret_file"; } ||
      { test -n "$grafana_netrc" && test -e "$grafana_netrc"; }; then
      printf 'Temporary production files remain after cleanup: %s\n' "$temp_dir" >&2
      cleanup_failed=1
    fi

    if test "${HAIUN_CHECK_FORCE_CLEANUP_FAILURE:-0}" = "1"; then
      cleanup_failed=1
    fi
    return "$cleanup_failed"
  }

  # shellcheck disable=SC2329  # Invoked indirectly by the EXIT trap.
  exit_production_smoke() {
    local original_status="$?"
    local cleanup_status=0
    local final_status

    trap - EXIT
    if test "$original_status" -ne 0 && test "$compose_started" = "1"; then
      docker compose -p "$production_project" -f compose.production.yml ps --all >&2 || true
      docker compose -p "$production_project" -f compose.production.yml \
        logs --no-color --tail=200 2>&1 |
        python3 -c '
from pathlib import Path
import sys

secret = Path(sys.argv[1]).read_text(encoding="utf-8").rstrip("\n")
sys.stdout.write(sys.stdin.read().replace(secret, "[REDACTED]"))
' "$secret_file" >&2 || true
    fi
    cleanup_production_smoke || cleanup_status="$?"
    if smoke_exit_status "$original_status" "$cleanup_status"; then
      final_status=0
    else
      final_status="$?"
    fi
    exit "$final_status"
  }

  assert_no_password_exposure() {
    local checker_pid="$BASHPID"
    local curl_pid="$1"
    local -a container_ids
    local exposure_snapshot

    mapfile -t container_ids < <(
      docker compose -p "$production_project" -f compose.production.yml ps -q
    )
    exposure_snapshot="$({
      tr '\0' '\n' <"/proc/$curl_pid/cmdline"
      tr '\0' '\n' <"/proc/$curl_pid/environ"
      tr '\0' '\n' <"/proc/$checker_pid/cmdline"
      tr '\0' '\n' <"/proc/$checker_pid/environ"
      docker inspect --format '{{json .Config.Env}} {{json .Path}} {{json .Args}}' \
        "${container_ids[@]}"
      docker top "$grafana_id" -eo pid,args
      docker exec --user 472 "$grafana_id" sh -c \
        "tr '\\0' '\\n' </proc/1/cmdline; tr '\\0' '\\n' </proc/1/environ"
    } 2>/dev/null)"

    if printf '%s' "$exposure_snapshot" | rg -F -f "$secret_file" -q; then
      printf 'Grafana password reached a running command line or environment.\n' >&2
      return 1
    fi
  }

  assert_host_port_available 80
  assert_host_port_available 3000

  production_project="haiun-check-production-$$"
  grafana_password="haiun-check-grafana-password"
  secret_owner="$(id -u)"
  edge_network="${production_project}-edge"
  monitoring_network="${production_project}-monitoring"
  data_volume="${production_project}-data"
  loki_volume="${production_project}-loki"
  prometheus_volume="${production_project}-prometheus"
  grafana_volume="${production_project}-grafana"
  compose_started=0
  credential_probe_pid=""
  temp_dir=""
  production_config_dir=""
  secret_file=""
  grafana_netrc=""

  export HAIUN_IMAGE=haiun-check:app
  export HAIUN_DATA_VOLUME="$data_volume"
  export HAIUN_TRUSTED_PROXIES_FILE="$root/deploy/nginx/trusted-proxies.default.conf"
  export HAIUN_LOKI_VOLUME="$loki_volume"
  export HAIUN_PROMETHEUS_VOLUME="$prometheus_volume"
  export HAIUN_GRAFANA_VOLUME="$grafana_volume"
  export HAIUN_EDGE_NETWORK="$edge_network"
  export HAIUN_MONITORING_NETWORK="$monitoring_network"

  temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/haiun-check-production.XXXXXX")"
  production_config_dir="$temp_dir/config"
  secret_file="$temp_dir/grafana_admin_password.txt"
  grafana_netrc="$temp_dir/grafana.netrc"
  trap exit_production_smoke EXIT

  mkdir -p "$production_config_dir"
  printf '%s\n' "$grafana_password" >"$secret_file"
  printf 'machine 127.0.0.1\nlogin admin\npassword %s\n' \
    "$grafana_password" >"$grafana_netrc"
  test "$(stat -c '%u:%a' "$secret_file")" = "${secret_owner}:600"
  test "$(stat -c '%u:%a' "$grafana_netrc")" = "${secret_owner}:600"

  export HAIUN_CONFIG_DIR="$production_config_dir"
  export GRAFANA_ADMIN_PASSWORD_FILE="$secret_file"

  if test -n "${HAIUN_CHECK_PRECOMPOSE_EXIT_STATUS:-}"; then
    exit "$HAIUN_CHECK_PRECOMPOSE_EXIT_STATUS"
  fi

  compose_started=1
  docker compose -p "$production_project" -f compose.production.yml up -d --no-build

  assert_memory() {
    local service="$1"
    local expected="$2"
    local container_id
    local actual
    container_id="$(docker compose -p "$production_project" -f compose.production.yml ps -q "$service")"
    actual="$(docker inspect --format '{{.HostConfig.Memory}}' "$container_id")"
    test "$actual" = "$expected"
  }

  assert_memory haiun 805306368
  assert_memory grafana 201326592
  assert_memory loki 201326592
  assert_memory prometheus 201326592
  assert_memory alloy 100663296
  assert_memory nginx 67108864

  nginx_id="$(docker compose -p "$production_project" -f compose.production.yml ps -q nginx)"
  grafana_id="$(docker compose -p "$production_project" -f compose.production.yml ps -q grafana)"
  grafana_security_ready=0
  grafana_uid=""
  grafana_secret_mode=""
  for _ in $(seq 1 30); do
    grafana_uid="$(docker exec "$grafana_id" sh -c \
      "awk '/^Uid:/ {print \$2}' /proc/1/status" 2>/dev/null || true)"
    grafana_secret_mode="$(docker exec "$grafana_id" stat -c '%u:%g:%a' \
      /run/haiun-secrets/grafana_admin_password 2>/dev/null || true)"
    if test "$grafana_uid" = "472" && test "$grafana_secret_mode" = "472:0:400"; then
      grafana_security_ready=1
      break
    fi
    sleep 1
  done
  if test "$grafana_security_ready" != "1"; then
    printf 'Grafana did not drop to UID 472 with a 0400 container secret; uid=%s mode=%s.\n' \
      "$grafana_uid" "$grafana_secret_mode" >&2
    exit 1
  fi
  test "$(stat -c '%u:%a' "$secret_file")" = "${secret_owner}:600"
  if docker inspect --format '{{json .Config.Env}} {{json .Path}} {{json .Args}}' \
    "$grafana_id" | rg -F -f "$secret_file" -q; then
    printf 'Grafana password reached configured environment or argv.\n' >&2
    exit 1
  fi
  if docker logs "$grafana_id" 2>&1 | rg -F -f "$secret_file" -q; then
    printf 'Grafana password reached container logs.\n' >&2
    exit 1
  fi
  docker inspect --format '{{json .HostConfig.PortBindings}}' "$nginx_id" |
    rg -q '"HostIp":"","HostPort":"80"'
  docker inspect --format '{{json .HostConfig.PortBindings}}' "$grafana_id" |
    rg -q '"HostIp":"127.0.0.1","HostPort":"3000"'
  for private_service in haiun alloy loki prometheus; do
    container_id="$(docker compose -p "$production_project" -f compose.production.yml ps -q "$private_service")"
    if docker inspect --format '{{json .HostConfig.PortBindings}}' "$container_id" |
      rg -q 'HostPort'; then
      printf '%s unexpectedly publishes a host port.\n' "$private_service" >&2
      exit 1
    fi
  done

  curl --fail --silent --show-error --retry 60 --retry-delay 1 --retry-connrefused \
    --retry-all-errors \
    http://127.0.0.1/api/health |
    python3 -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ok"'

  test "$(curl --silent --output /dev/null --write-out '%{http_code}' \
    http://127.0.0.1/metrics)" = "404"

  curl --fail --silent --show-error \
    -H 'X-Forwarded-For: 203.0.113.42' \
    -H 'X-Forwarded-Proto: https' \
    -H 'Referer: https://example.com/private/path?oauth_token=must-not-log' \
    -H 'User-Agent: HaiunDeploymentCheck/1.0' \
    'http://127.0.0.1/api/health?oauth_token=must-not-log' >/dev/null

  prometheus_ready=0
  for _ in $(seq 1 60); do
    if query_monitoring_service "$monitoring_network" --fail --silent --get \
      --data-urlencode 'query=up{job=~"haiun|prometheus|loki|alloy"}' \
      http://prometheus:9090/api/v1/query |
      python3 -c '
import json, sys
payload = json.load(sys.stdin)
assert payload["status"] == "success"
results = {
    item["metric"]["job"]: item["value"][1]
    for item in payload["data"]["result"]
}
assert results == {
    "haiun": "1",
    "prometheus": "1",
    "loki": "1",
    "alloy": "1",
}
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
    --retry-all-errors \
    http://127.0.0.1:3000/api/health |
    python3 -c 'import json, sys; assert json.load(sys.stdin)["database"] == "ok"'

  curl --fail --silent --show-error \
    --netrc-file "$grafana_netrc" \
    --limit-rate 1 \
    --max-time 30 \
    'http://127.0.0.1:3000/api/search?query=Haiun' >/dev/null 2>&1 &
  credential_probe_pid="$!"
  credential_probe_seen=0
  for _ in $(seq 1 30); do
    if kill -0 "$credential_probe_pid" 2>/dev/null &&
      test -r "/proc/$credential_probe_pid/cmdline"; then
      assert_no_password_exposure "$credential_probe_pid"
      credential_probe_seen=1
      break
    fi
    sleep 0.1
  done
  test "$credential_probe_seen" = "1"
  kill "$credential_probe_pid" >/dev/null 2>&1 || true
  wait "$credential_probe_pid" >/dev/null 2>&1 || true
  credential_probe_pid=""

  dashboards_ready=0
  for _ in $(seq 1 30); do
    if curl --fail --silent --show-error \
      --netrc-file "$grafana_netrc" \
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

  test "$(stat -c '%u:%a' "$secret_file")" = "${secret_owner}:600"
  test "$(stat -c '%u:%a' "$grafana_netrc")" = "${secret_owner}:600"
  if docker logs "$grafana_id" 2>&1 | rg -F -f "$secret_file" -q; then
    printf 'Grafana password reached container logs.\n' >&2
    exit 1
  fi
)

check_precompose_cleanup() {
  local actual_status
  local injection_root
  local leftovers

  injection_root="$(mktemp -d "${TMPDIR:-/tmp}/haiun-precompose-check.XXXXXX")"

  if TMPDIR="$injection_root" \
    HAIUN_CHECK_PRECOMPOSE_EXIT_STATUS=0 \
    HAIUN_CHECK_FORCE_CLEANUP_FAILURE=1 \
    smoke_production; then
    actual_status=0
  else
    actual_status="$?"
  fi
  leftovers="$(find "$injection_root" -mindepth 1 -print -quit)"
  if test "$actual_status" != "1" || test -n "$leftovers"; then
    rm -rf "$injection_root"
    return 1
  fi

  if TMPDIR="$injection_root" \
    HAIUN_CHECK_PRECOMPOSE_EXIT_STATUS=7 \
    HAIUN_CHECK_FORCE_CLEANUP_FAILURE=1 \
    smoke_production; then
    actual_status=0
  else
    actual_status="$?"
  fi
  leftovers="$(find "$injection_root" -mindepth 1 -print -quit)"
  rm -rf "$injection_root"
  test "$actual_status" = "7"
  test -z "$leftovers"
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
  production)
    check_production_config
    smoke_production
    ;;
  all)
    check_simple_config
    smoke_simple
    check_nginx_config
    check_telemetry_config
    check_grafana_config
    check_production_config
    smoke_production
    ;;
  *)
    printf 'Usage: %s [simple|nginx|telemetry|grafana|production|all]\n' "$0" >&2
    exit 2
    ;;
esac

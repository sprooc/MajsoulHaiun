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
  all)
    check_simple_config
    smoke_simple
    check_nginx_config
    check_telemetry_config
    ;;
  *)
    printf 'Usage: %s [simple|nginx|telemetry|all]\n' "$0" >&2
    exit 2
    ;;
esac

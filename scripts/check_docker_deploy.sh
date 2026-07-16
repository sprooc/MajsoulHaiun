#!/usr/bin/env bash
set -euo pipefail

root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

mode="${1:-all}"

check_simple_config() {
  docker build \
    --build-arg PYPI_INDEX_URL="${HAIUN_PYPI_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
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

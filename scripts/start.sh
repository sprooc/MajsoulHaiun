#!/usr/bin/env bash
set -euo pipefail

root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

export HAIUN_DATA_DIR="${HAIUN_DATA_DIR:-$root/data}"
host="${HAIUN_HOST:-0.0.0.0}"
port="${HAIUN_PORT:-8765}"
config_path="${HAIUN_CONFIG:-$root/config/config.toml}"
mkdir -p "$HAIUN_DATA_DIR"

if [ ! -x "$root/.venv/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv "$root/.venv"
  else
    "${PYTHON:-python3}" -m venv "$root/.venv"
  fi
fi
if ! "$root/.venv/bin/python" -c 'import fastapi' >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$root/.venv/bin/python" -e .
  else
    "$root/.venv/bin/python" -m pip install -e .
  fi
fi
if [ ! -d "$root/frontend/node_modules" ]; then
  npm --prefix "$root/frontend" install
fi

needs_build=0
if [ ! -f "$root/frontend/dist/index.html" ]; then
  needs_build=1
elif [ -n "$(find "$root/frontend/src" "$root/frontend/index.html" -type f -newer "$root/frontend/dist/index.html" -print -quit)" ]; then
  needs_build=1
elif [ "${HAIUN_REBUILD:-0}" = "1" ]; then
  needs_build=1
fi
if [ "$needs_build" = "1" ]; then
  npm --prefix "$root/frontend" run build
fi

loopback_url="http://127.0.0.1:$port"
printf '牌运 Haiun\nLoopback: %s\n' "$loopback_url"
if [ "$host" = "0.0.0.0" ]; then
  for address in $(hostname -I 2>/dev/null || true); do
    case "$address" in
      *:*) printf 'LAN:      http://[%s]:%s\n' "$address" "$port" ;;
      *) printf 'LAN:      http://%s:%s\n' "$address" "$port" ;;
    esac
  done
  if [ ! -f "$config_path" ] || ! grep -Eq '^[[:space:]]*\[admin\][[:space:]]*$' "$config_path"; then
    printf 'Warning: administrator access is not configured; /admin login will remain locked.\n'
  fi
  printf 'Public deployment requires a TLS reverse proxy, firewall policy, and request limiting.\n'
fi

if [ "${HAIUN_OPEN_BROWSER:-1}" != "0" ] && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$loopback_url" >/dev/null 2>&1 &
fi

export PYTHONPATH="$root/backend"
exec "$root/.venv/bin/python" -m uvicorn app.main:app --host "$host" --port "$port"

#!/usr/bin/env bash
set -euo pipefail

root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

export HAIUN_DATA_DIR="${HAIUN_DATA_DIR:-$root/data}"
export HAIUN_HOST="${HAIUN_HOST:-0.0.0.0}"
export HAIUN_PORT="${HAIUN_PORT:-8765}"
export HAIUN_FRONTEND_HOST="${HAIUN_FRONTEND_HOST:-$HAIUN_HOST}"
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
    uv pip install --python "$root/.venv/bin/python" -e '.[test]'
  else
    "$root/.venv/bin/python" -m pip install -e '.[test]'
  fi
fi
if [ ! -d "$root/frontend/node_modules" ]; then
  npm --prefix "$root/frontend" install
fi

backend_pid=""
frontend_pid=""
cleanup() {
  trap - EXIT INT TERM
  [ -z "$backend_pid" ] || kill "$backend_pid" 2>/dev/null || true
  [ -z "$frontend_pid" ] || kill "$frontend_pid" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

PYTHONPATH="$root/backend" "$root/.venv/bin/python" -m uvicorn app.main:app \
  --host "$HAIUN_HOST" --port "$HAIUN_PORT" --reload --reload-dir "$root/backend" &
backend_pid=$!

npm --prefix "$root/frontend" run dev -- --host "$HAIUN_FRONTEND_HOST" &
frontend_pid=$!

printf '牌运开发环境\nAPI: http://127.0.0.1:%s\nUI:  http://127.0.0.1:5173\n' "$HAIUN_PORT"
wait -n "$backend_pid" "$frontend_pid"

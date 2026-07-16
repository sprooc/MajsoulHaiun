# syntax=docker/dockerfile:1.7
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/
ARG PYPI_INDEX_URL=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend \
    HAIUN_DATA_DIR=/data \
    HAIUN_CONFIG=/app/config/config.toml
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY backend/ ./backend/
RUN uv export --frozen --no-dev --no-emit-project --format requirements-txt \
      --output-file /tmp/requirements.txt \
    && python -m venv /app/.venv \
    && /app/.venv/bin/pip install --no-cache-dir --index-url "$PYPI_INDEX_URL" \
      --require-hashes --requirement /tmp/requirements.txt \
    && /app/.venv/bin/pip install --no-cache-dir --index-url "$PYPI_INDEX_URL" \
      --no-deps . \
    && rm -rf /root/.cache/pip /tmp/requirements.txt
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
RUN groupadd --system --gid 10001 haiun \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --no-create-home haiun \
    && mkdir -p /data /app/config \
    && chown haiun:haiun /data \
    && chmod 0755 /app /app/config /app/backend /app/backend/app \
    && chmod 0555 /app/backend/app/docker_entrypoint.py
USER haiun
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["/usr/local/bin/python", "-I", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=3).read()"]
ENTRYPOINT ["/usr/local/bin/python", "-I", "/app/backend/app/docker_entrypoint.py"]
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]

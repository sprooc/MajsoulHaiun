from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.access import router as access_router
from app.api.analyses import router as analysis_router
from app.api.replays import router as replay_router
from app.api.sources import router as source_router
from app.config import REPOSITORY_ROOT, Settings
from app.config_file import load_haiun_config
from app.auth import AdminLoginLimiter
from app.algorithms.baseline_v1 import BaselineV1
from app.algorithms.registry import AlgorithmRegistry
from app.db import Base, create_session_factory
from app.errors import AppError
from app.sources.amae_koromo import AmaeKoromoSource
from app.sources.registry import SourceRegistry
from app import models  # noqa: F401


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    resolved.data_dir.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = application.state.session_factory.kw["bind"]
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield
        await application.state.http_client.aclose()
        await engine.dispose()

    app = FastAPI(title="牌运 Haiun", version=resolved.version, lifespan=lifespan)
    app.state.settings = resolved
    app.state.file_config = load_haiun_config(resolved.config_path, missing_ok=True)
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
        app.mount("/", StaticFiles(directory=static_directory, html=True), name="frontend")
    return app


app = create_app()

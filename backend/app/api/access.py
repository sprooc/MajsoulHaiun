from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, SecretStr

from app.auth import ADMIN_COOKIE_NAME, client_key, is_admin_request, password_matches
from app.errors import AppError
from app.repositories.access_repository import AccessRepository


router = APIRouter(prefix="/api", tags=["access"])


class AdminSessionRequest(BaseModel):
    secret: SecretStr


@router.get("/access")
async def get_access(request: Request) -> dict[str, str]:
    return {"role": "admin" if await is_admin_request(request) else "guest"}


@router.post("/admin/session", include_in_schema=False)
async def create_admin_session(
    request: Request,
    response: Response,
    body: AdminSessionRequest,
) -> dict[str, str]:
    limiter = request.app.state.admin_login_limiter
    key = client_key(request)
    if limiter.is_limited(key):
        raise AppError(
            "ADMIN_AUTH_RATE_LIMITED",
            "Administrator authentication is temporarily unavailable.",
            status_code=429,
        )

    admin = request.app.state.file_config.admin
    submitted = body.secret.get_secret_value()
    if admin is None or not password_matches(
        submitted,
        admin.password.get_secret_value(),
    ):
        limiter.record_failure(key)
        raise AppError(
            "ADMIN_AUTH_FAILED",
            "Administrator authentication failed.",
            status_code=401,
        )

    limiter.reset(key)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=admin.session_hours)
    session = request.app.state.session_factory()
    try:
        raw_token = await AccessRepository(session).create_admin_session(expires_at)
    finally:
        await session.close()
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        raw_token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=admin.session_hours * 3600,
        path="/",
    )
    return {"role": "admin"}


@router.delete("/admin/session", include_in_schema=False)
async def delete_admin_session(request: Request, response: Response) -> dict[str, str]:
    session = request.app.state.session_factory()
    try:
        await AccessRepository(session).revoke_admin_token(
            request.cookies.get(ADMIN_COOKIE_NAME)
        )
    finally:
        await session.close()
    response.delete_cookie(
        ADMIN_COOKIE_NAME,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return {"role": "guest"}

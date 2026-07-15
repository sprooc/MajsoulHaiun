import hashlib
import hmac
import time
from collections import deque

from fastapi import Request

from app.errors import AppError
from app.repositories.access_repository import AccessRepository


ADMIN_COOKIE_NAME = "haiun_admin_session"


class AdminLoginLimiter:
    def __init__(self, *, max_failures: int = 5, window_seconds: int = 300):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str) -> deque[float]:
        failures = self._failures.get(key)
        if failures is None:
            return deque()
        cutoff = time.monotonic() - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            self._failures.pop(key, None)
        return failures

    def is_limited(self, key: str) -> bool:
        return len(self._recent(key)) >= self.max_failures

    def record_failure(self, key: str) -> None:
        failures = self._recent(key)
        failures.append(time.monotonic())
        self._failures[key] = failures

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


def client_key(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def password_matches(submitted: str, configured: str) -> bool:
    submitted_hash = hashlib.sha256(submitted.encode("utf-8")).digest()
    configured_hash = hashlib.sha256(configured.encode("utf-8")).digest()
    return hmac.compare_digest(submitted_hash, configured_hash)


async def is_admin_request(request: Request) -> bool:
    session = request.app.state.session_factory()
    try:
        return await AccessRepository(session).is_admin_token(
            request.cookies.get(ADMIN_COOKIE_NAME)
        )
    finally:
        await session.close()


async def require_admin(request: Request) -> None:
    if not await is_admin_request(request):
        raise AppError(
            "ADMIN_ACCESS_REQUIRED",
            "Administrator access is required.",
            status_code=403,
        )

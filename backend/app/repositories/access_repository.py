import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import AdminSessionModel


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AccessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_admin_session(self, expires_at: datetime) -> str:
        raw_token = secrets.token_urlsafe(32)
        self.session.add(
            AdminSessionModel(
                token_hash=_token_hash(raw_token),
                expires_at=expires_at,
            )
        )
        await self.session.commit()
        return raw_token

    async def is_admin_token(self, raw_token: str | None) -> bool:
        if not raw_token:
            return False
        model = await self.session.scalar(
            select(AdminSessionModel).where(
                AdminSessionModel.token_hash == _token_hash(raw_token)
            )
        )
        if model is None:
            return False
        if _as_utc(model.expires_at) <= datetime.now(timezone.utc):
            await self.session.delete(model)
            await self.session.commit()
            return False
        return True

    async def revoke_admin_token(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        model = await self.session.scalar(
            select(AdminSessionModel).where(
                AdminSessionModel.token_hash == _token_hash(raw_token)
            )
        )
        if model is not None:
            await self.session.delete(model)
            await self.session.commit()

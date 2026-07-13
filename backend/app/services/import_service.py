from uuid import UUID

from app.errors import AppError
from app.repositories.replay_repository import ReplayRepository
from app.sources.local_file import validate_replay_file
from app.sources.majsoul.fetcher import MajsoulReplayFetcher, ReplayFetchUnavailable
from app.sources.majsoul.locator import MajsoulLocator


class ImportService:
    def __init__(self, repository: ReplayRepository, replay_fetcher: MajsoulReplayFetcher):
        self.repository = repository
        self.replay_fetcher = replay_fetcher

    async def import_file(self, filename: str, payload: bytes, content_type: str | None = None) -> UUID:
        validate_replay_file(filename, payload)
        return await self.repository.put_bytes(
            source="local-file",
            external_id=filename,
            payload=payload,
            filename=filename,
            content_type=content_type,
        )

    async def import_remote(self, value: str) -> UUID:
        try:
            locator = MajsoulLocator.parse(value)
        except ValueError as exc:
            raise AppError("INVALID_REPLAY_LOCATOR", "Invalid Mahjong Soul replay link or ID.", status_code=422) from exc
        try:
            payload = await self.replay_fetcher.fetch(locator)
        except ReplayFetchUnavailable as exc:
            raise AppError(
                "REPLAY_FETCH_UNAVAILABLE",
                "Anonymous raw-replay access is unavailable; import a local replay file instead.",
                status_code=503,
                parameters={"recordId": locator.record_id},
            ) from exc
        return await self.repository.put_bytes(source="majsoul", external_id=locator.record_id, payload=payload)

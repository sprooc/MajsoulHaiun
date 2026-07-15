from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, ValidationError

from app.errors import AppError
from app.domain.game import CanonicalGame
from app.repositories.replay_repository import ReplayRepository
from app.services.import_service import ImportService
from app.sources.majsoul.canonicalizer import canonicalize_majsoul
from app.sources.majsoul.decoder import decode_majsoul
from app.sources.majsoul.fetcher import MajsoulReplayFetcher
from app.auth import require_admin


router = APIRouter(prefix="/api/replays", tags=["replays"])


class LocatorImport(BaseModel):
    locator: str


async def _service(request: Request):
    session = request.app.state.session_factory()
    repository = ReplayRepository(session)
    fetcher = MajsoulReplayFetcher(
        request.app.state.settings.config_path,
        request.app.state.http_client,
    )
    return session, repository, ImportService(repository, fetcher)


async def _store_canonical_game(
    repository: ReplayRepository,
    replay_id: UUID,
    payload: bytes,
) -> dict[str, str]:
    response = {"replayId": str(replay_id)}
    schema_version = str(CanonicalGame.model_fields["schema_version"].default)
    existing_game_id = await repository.get_game_id_for_replay(replay_id, schema_version)
    if existing_game_id is not None:
        response["gameId"] = str(existing_game_id)
        return response
    try:
        decoded = decode_majsoul(payload)
        if "schema_version" in decoded and "players" in decoded:
            game = CanonicalGame.model_validate(decoded)
        else:
            game = canonicalize_majsoul(decoded)
        game_id = await repository.put_canonical_game(replay_id, game)
        response["gameId"] = str(game_id)
    except AppError as exc:
        response["parseErrorCode"] = exc.code
    except (ValidationError, ValueError, TypeError):
        response["parseErrorCode"] = "INVALID_REPLAY_DATA"
    return response


@router.post("/import-file")
async def import_file(request: Request, file: UploadFile = File()) -> dict[str, str]:
    session, repository, service = await _service(request)
    try:
        payload = await file.read()
        replay_id = await service.import_file(file.filename or "replay.bin", payload, file.content_type)
        return await _store_canonical_game(repository, replay_id, payload)
    finally:
        await session.close()


@router.post("/import-locator")
async def import_locator(request: Request, body: LocatorImport) -> dict[str, str]:
    session, repository, service = await _service(request)
    try:
        replay_id = await service.import_remote(body.locator)
        replay = await repository.get(replay_id)
        if replay is None:
            raise AppError("REPLAY_NOT_FOUND", "Imported replay was not found.", status_code=500)
        response = await _store_canonical_game(repository, replay_id, replay.payload)
        if "parseErrorCode" in response:
            await repository.delete(replay_id)
            raise AppError(
                response["parseErrorCode"],
                "Fetched Mahjong Soul replay could not be parsed.",
                status_code=422,
                parameters={"recordId": replay.external_id},
            )
        return response
    finally:
        await session.close()


@router.get("/{replay_id}")
async def get_replay(request: Request, replay_id: UUID) -> dict[str, object]:
    session = request.app.state.session_factory()
    try:
        replay = await ReplayRepository(session).get(replay_id)
        if replay is None:
            raise AppError("REPLAY_NOT_FOUND", "Replay was not found.", status_code=404)
        return {
            "id": str(replay.id),
            "source": replay.source,
            "externalId": replay.external_id,
            "sha256": replay.sha256,
            "filename": replay.filename,
        }
    finally:
        await session.close()


@router.delete("/{replay_id}")
async def delete_replay(
    request: Request,
    replay_id: UUID,
    _admin: None = Depends(require_admin),
) -> dict[str, bool]:
    session = request.app.state.session_factory()
    try:
        deleted = await ReplayRepository(session).delete(replay_id)
        if not deleted:
            raise AppError("REPLAY_NOT_FOUND", "Replay was not found.", status_code=404)
        return {"deleted": True}
    finally:
        await session.close()

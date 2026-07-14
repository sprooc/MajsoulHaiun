from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.errors import AppError
from app.repositories.replay_repository import RawReplayRecord
from app.services.import_service import ImportService
from app.sources.majsoul.fetcher import ReplayFetchUnavailable


@pytest.fixture
def repository():
    repository = AsyncMock()
    repository.get_by_source_external_id.return_value = None
    repository.put_bytes.return_value = uuid4()
    return repository


@pytest.fixture
def replay_fetcher():
    return AsyncMock()


@pytest.fixture
def import_service(repository, replay_fetcher):
    return ImportService(repository, replay_fetcher)


async def test_file_import_rejects_more_than_32_mib(import_service):
    with pytest.raises(AppError) as error:
        await import_service.import_file("large.bin", b"x" * (32 * 1024 * 1024 + 1))
    assert error.value.code == "REPLAY_FILE_TOO_LARGE"


async def test_remote_import_maps_fetch_unavailable(import_service, replay_fetcher):
    replay_fetcher.fetch.side_effect = ReplayFetchUnavailable()
    with pytest.raises(AppError) as error:
        await import_service.import_remote("260307-76323960-cf3c-494e-be24-26dd6ba81c98")
    assert error.value.code == "REPLAY_FETCH_UNAVAILABLE"


async def test_remote_import_returns_cached_replay_without_fetching(import_service, repository, replay_fetcher):
    cached = RawReplayRecord(
        id=uuid4(),
        source="majsoul",
        external_id="260307-76323960-cf3c-494e-be24-26dd6ba81c98",
        payload=b"cached",
        sha256="digest",
        filename=None,
        content_type=None,
    )
    repository.get_by_source_external_id.return_value = cached

    replay_id = await import_service.import_remote(cached.external_id)

    assert replay_id == cached.id
    replay_fetcher.fetch.assert_not_awaited()
    repository.put_bytes.assert_not_awaited()


async def test_remote_import_stores_fetched_replay_by_majsoul_identity(import_service, repository, replay_fetcher):
    replay_fetcher.fetch.return_value = b"wrapped"

    replay_id = await import_service.import_remote("260307-76323960-cf3c-494e-be24-26dd6ba81c98")

    assert replay_id == repository.put_bytes.return_value
    repository.put_bytes.assert_awaited_once_with(
        source="majsoul",
        external_id="260307-76323960-cf3c-494e-be24-26dd6ba81c98",
        payload=b"wrapped",
    )


async def test_file_import_hashes_payload_through_repository(import_service, repository):
    replay_id = await import_service.import_file("game.json", b'{"schema_version":"1.0.0"}', "application/json")
    assert replay_id == repository.put_bytes.return_value
    repository.put_bytes.assert_awaited_once_with(
        source="local-file",
        external_id="game.json",
        payload=b'{"schema_version":"1.0.0"}',
        filename="game.json",
        content_type="application/json",
    )


async def test_executable_archives_are_rejected(import_service):
    with pytest.raises(AppError) as error:
        await import_service.import_file("payload.exe", b"MZpayload")
    assert error.value.code == "UNSUPPORTED_REPLAY_FILE"

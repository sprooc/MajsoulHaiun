from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.errors import AppError
from app.services.import_service import ImportService
from app.sources.majsoul.fetcher import ReplayFetchUnavailable


@pytest.fixture
def repository():
    repository = AsyncMock()
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


async def test_remote_import_does_not_request_credentials(import_service, replay_fetcher):
    replay_fetcher.fetch.side_effect = ReplayFetchUnavailable()
    with pytest.raises(AppError) as error:
        await import_service.import_remote("260307-76323960-cf3c-494e-be24-26dd6ba81c98")
    assert error.value.code == "REPLAY_FETCH_UNAVAILABLE"


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

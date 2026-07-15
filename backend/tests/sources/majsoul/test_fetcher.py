from pathlib import Path

import httpx
import pytest

from app.sources.majsoul.client import MajsoulGatewayError, MajsoulLoginRejected, MajsoulRecordUnavailable
from app.sources.majsoul.fetcher import (
    MajsoulReplayFetcher,
    ReplayFetchConfigurationError,
    ReplayFetchRemoteError,
    ReplayFetchUnavailable,
)
from app.sources.majsoul.locator import MajsoulLocator


RECORD_ID = "260714-ec4c890c-abec-4758-9337-2bce7085dbe6"


class FakeClientFactory:
    def __init__(self, results: list[bytes | Exception]):
        self.results = list(results)
        self.usernames: list[str] = []
        self.hosts: list[str] = []
        self.timeouts: list[float] = []

    def __call__(self, *, host: str, timeout_seconds: float, http_client: httpx.AsyncClient):
        self.hosts.append(host)
        self.timeouts.append(timeout_seconds)
        result = self.results[len(self.hosts) - 1]
        factory = self

        class FakeClient:
            async def fetch_record(self, record_id: str, username: str, password: str) -> bytes:
                factory.usernames.append(username)
                assert record_id == RECORD_ID
                assert password.startswith("secret-")
                if isinstance(result, Exception):
                    raise result
                return result

        return FakeClient()


def write_config(path: Path):
    path.write_text(
        "timeout_seconds = 9\n"
        "[[accounts]]\n"
        'username = "first"\n'
        'password = "secret-one"\n'
        'host = "https://game.maj-soul.com"\n'
        "[[accounts]]\n"
        'username = "second"\n'
        'password = "secret-two"\n'
        'host = "https://game.maj-soul.com"\n',
        encoding="utf-8",
    )


def build_fetcher(tmp_path: Path, results: list[bytes | Exception]):
    config_path = tmp_path / "config.toml"
    write_config(config_path)
    factory = FakeClientFactory(results)
    fetcher = MajsoulReplayFetcher(
        config_path=config_path,
        http_client=httpx.AsyncClient(),
        client_factory=factory,
    )
    return fetcher, factory


async def test_tries_accounts_in_toml_order_after_login_rejection(tmp_path: Path):
    fetcher, factory = build_fetcher(tmp_path, [MajsoulLoginRejected(), b"wrapped-replay"])

    try:
        payload = await fetcher.fetch(MajsoulLocator.parse(RECORD_ID))
    finally:
        await fetcher.http_client.aclose()

    assert payload == b"wrapped-replay"
    assert factory.usernames == ["first", "second"]
    assert factory.hosts == ["https://game.maj-soul.com", "https://game.maj-soul.com"]
    assert factory.timeouts == [9, 9]


async def test_tries_next_account_after_record_1203(tmp_path: Path):
    fetcher, factory = build_fetcher(tmp_path, [MajsoulRecordUnavailable(), b"wrapped-replay"])

    try:
        payload = await fetcher.fetch(MajsoulLocator.parse(RECORD_ID))
    finally:
        await fetcher.http_client.aclose()

    assert payload == b"wrapped-replay"
    assert factory.usernames == ["first", "second"]


async def test_stops_on_gateway_failure(tmp_path: Path):
    fetcher, factory = build_fetcher(tmp_path, [MajsoulGatewayError("gateway unavailable"), b"must-not-run"])

    try:
        with pytest.raises(ReplayFetchRemoteError):
            await fetcher.fetch(MajsoulLocator.parse(RECORD_ID))
    finally:
        await fetcher.http_client.aclose()

    assert factory.usernames == ["first"]


async def test_all_accounts_rejected_returns_sanitized_unavailable(tmp_path: Path):
    fetcher, _ = build_fetcher(tmp_path, [MajsoulLoginRejected(), MajsoulRecordUnavailable()])

    try:
        with pytest.raises(ReplayFetchUnavailable) as error:
            await fetcher.fetch(MajsoulLocator.parse(RECORD_ID))
    finally:
        await fetcher.http_client.aclose()

    assert "first" not in str(error.value)
    assert "second" not in str(error.value)
    assert "secret" not in str(error.value)


async def test_missing_config_is_typed_and_sanitized(tmp_path: Path):
    http_client = httpx.AsyncClient()
    fetcher = MajsoulReplayFetcher(
        config_path=tmp_path / "missing.toml",
        http_client=http_client,
        client_factory=FakeClientFactory([]),
    )

    try:
        with pytest.raises(ReplayFetchConfigurationError) as error:
            await fetcher.fetch(MajsoulLocator.parse(RECORD_ID))
    finally:
        await http_client.aclose()

    assert "password" not in str(error.value).lower()


async def test_client_factory_failure_is_mapped_to_remote_error(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    write_config(config_path)
    http_client = httpx.AsyncClient()

    def broken_factory(**_kwargs):
        raise RuntimeError("constructor failed")

    fetcher = MajsoulReplayFetcher(config_path, http_client, broken_factory)
    try:
        with pytest.raises(ReplayFetchRemoteError):
            await fetcher.fetch(MajsoulLocator.parse(RECORD_ID))
    finally:
        await http_client.aclose()

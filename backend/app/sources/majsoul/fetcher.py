from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from app.config import REPOSITORY_ROOT
from app.sources.majsoul.client import (
    MajsoulClient,
    MajsoulClientError,
    MajsoulLoginRejected,
    MajsoulRecordUnavailable,
)
from app.sources.majsoul.fetch_config import MajsoulConfigError, load_majsoul_fetch_config
from app.sources.majsoul.locator import MajsoulLocator


class ReplayFetchUnavailable(Exception):
    pass


class ReplayFetchConfigurationError(ReplayFetchUnavailable):
    pass


class ReplayFetchRemoteError(ReplayFetchUnavailable):
    pass


class MajsoulReplayFetcher:
    def __init__(
        self,
        config_path: Path | None = None,
        http_client: httpx.AsyncClient | None = None,
        client_factory: Callable[..., Any] = MajsoulClient,
    ):
        self.config_path = config_path or REPOSITORY_ROOT / "config" / "majsoul.toml"
        self.http_client = http_client or httpx.AsyncClient()
        self.client_factory = client_factory

    async def fetch(self, locator: MajsoulLocator) -> bytes:
        try:
            config = load_majsoul_fetch_config(self.config_path)
        except MajsoulConfigError as exc:
            raise ReplayFetchConfigurationError("Mahjong Soul replay fetching is not configured.") from exc

        for account in config.accounts:
            client = self.client_factory(
                host=account.host,
                timeout_seconds=config.timeout_seconds,
                http_client=self.http_client,
            )
            try:
                return await client.fetch_record(
                    locator.record_id,
                    account.username,
                    account.password.get_secret_value(),
                )
            except (MajsoulLoginRejected, MajsoulRecordUnavailable):
                continue
            except MajsoulClientError as exc:
                raise ReplayFetchRemoteError("Mahjong Soul replay service request failed.") from exc

        raise ReplayFetchUnavailable("No configured Mahjong Soul account could access this replay.")

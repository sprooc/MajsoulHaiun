import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.sources.majsoul.fetch_config import MajsoulAccount, MajsoulFetchConfig


class HaiunConfigError(Exception):
    pass


class AdminConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    password: SecretStr = Field(repr=False, min_length=12)
    session_hours: int = Field(default=12, ge=1, le=24 * 30)


class HaiunFileConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    accounts: tuple[MajsoulAccount, ...] = ()
    admin: AdminConfig | None = None

    @property
    def majsoul(self) -> MajsoulFetchConfig:
        return MajsoulFetchConfig(
            timeout_seconds=self.timeout_seconds,
            accounts=self.accounts,
        )


def load_haiun_config(path: Path, *, missing_ok: bool = False) -> HaiunFileConfig:
    try:
        with path.open("rb") as config_file:
            raw = tomllib.load(config_file)
    except FileNotFoundError:
        if missing_ok:
            return HaiunFileConfig()
        raise HaiunConfigError(f"Haiun configuration file was not found: {path}") from None
    except (OSError, tomllib.TOMLDecodeError):
        raise HaiunConfigError(f"Invalid Haiun configuration file: {path}") from None

    try:
        return HaiunFileConfig.model_validate(raw)
    except ValidationError:
        raise HaiunConfigError(f"Invalid Haiun configuration file: {path}") from None

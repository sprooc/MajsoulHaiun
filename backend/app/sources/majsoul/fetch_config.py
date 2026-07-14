import tomllib
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from app.sources.majsoul.locator import ALLOWED_HOSTS


DEFAULT_MAJSOUL_HOST = "https://game.maj-soul.com"


class MajsoulConfigError(Exception):
    pass


class MajsoulAccount(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str
    password: SecretStr
    host: str = DEFAULT_MAJSOUL_HOST

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("account identifier is empty")
        return normalized

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: object) -> object:
        if not isinstance(value, str) or not value:
            raise ValueError("account secret is empty")
        return value

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        normalized = value.rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.path:
            raise ValueError("unsupported Mahjong Soul host")
        return normalized


class MajsoulFetchConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    accounts: tuple[MajsoulAccount, ...] = Field(min_length=1)


def load_majsoul_fetch_config(path: Path) -> MajsoulFetchConfig:
    try:
        with path.open("rb") as config_file:
            raw = tomllib.load(config_file)
    except FileNotFoundError as exc:
        raise MajsoulConfigError(f"Mahjong Soul configuration file was not found: {path}") from exc
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise MajsoulConfigError(f"Invalid Mahjong Soul configuration file: {path}") from exc

    try:
        return MajsoulFetchConfig.model_validate(raw)
    except ValidationError as exc:
        raise MajsoulConfigError(f"Invalid Mahjong Soul configuration file: {path}") from exc

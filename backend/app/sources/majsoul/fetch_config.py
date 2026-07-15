from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

DEFAULT_MAJSOUL_HOST = "https://game.maj-soul.com"


class MajsoulConfigError(Exception):
    pass


class MajsoulAccount(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str = Field(repr=False)
    password: SecretStr = Field(repr=False)
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
        if normalized != DEFAULT_MAJSOUL_HOST:
            raise ValueError("unsupported Mahjong Soul host")
        return normalized


class MajsoulFetchConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    accounts: tuple[MajsoulAccount, ...] = Field(min_length=1)


def load_majsoul_fetch_config(path: Path) -> MajsoulFetchConfig:
    from app.config_file import HaiunConfigError, load_haiun_config

    try:
        config = load_haiun_config(path)
    except HaiunConfigError:
        raise MajsoulConfigError(f"Invalid Mahjong Soul configuration file: {path}") from None
    if config.majsoul is None:
        raise MajsoulConfigError(f"Invalid Mahjong Soul configuration file: {path}") from None
    return config.majsoul

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

    majsoul: MajsoulFetchConfig | None = None
    admin: AdminConfig | None = None

    @property
    def timeout_seconds(self) -> float:
        return self.majsoul.timeout_seconds if self.majsoul is not None else 15.0

    @property
    def accounts(self) -> tuple[MajsoulAccount, ...]:
        return self.majsoul.accounts if self.majsoul is not None else ()


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

    majsoul = None
    majsoul_raw = {
        key: raw[key]
        for key in ("timeout_seconds", "accounts")
        if key in raw
    }
    if majsoul_raw:
        try:
            majsoul = MajsoulFetchConfig.model_validate(majsoul_raw)
        except ValidationError:
            pass

    admin = None
    if "admin" in raw:
        try:
            admin = AdminConfig.model_validate(raw["admin"])
        except ValidationError:
            pass

    return HaiunFileConfig(majsoul=majsoul, admin=admin)

from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HAIUN_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8765
    data_dir: Path = REPOSITORY_ROOT / "data"
    version: str = "0.1.0"
    allowed_origins: Annotated[tuple[str, ...], NoDecode] = ()

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.data_dir / 'haiun.sqlite3'}"

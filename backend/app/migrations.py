from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


ALEMBIC_CONFIG_PATH = Path(__file__).resolve().parents[1] / "alembic.ini"


def _sync_database_url(database_url: str) -> str:
    return database_url.replace("+aiosqlite", "")


def _unversioned_revision(database_url: str) -> str | None:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        if not tables or "alembic_version" in tables:
            return None
        if {"admin_sessions", "analysis_submissions"}.issubset(tables):
            return "0003_public_access"
        unique_constraints = inspector.get_unique_constraints("raw_replays")
        if any(
            constraint.get("name") == "uq_raw_replays_source_external"
            for constraint in unique_constraints
        ):
            return "0002_cache_raw_replay_identity"
        return "0001_initial"
    finally:
        engine.dispose()


def upgrade_database(database_url: str) -> None:
    sync_url = _sync_database_url(database_url)
    alembic_config = Config(str(ALEMBIC_CONFIG_PATH))
    alembic_config.attributes["database_url"] = sync_url
    existing_revision = _unversioned_revision(sync_url)
    if existing_revision is not None:
        command.stamp(alembic_config, existing_revision)
    command.upgrade(alembic_config, "head")

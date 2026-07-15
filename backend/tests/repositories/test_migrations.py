from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_identity_cache_migration_removes_dependent_rows_from_duplicate_game(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HAIUN_DATA_DIR", str(data_dir))
    alembic_config = Config("backend/alembic.ini")
    command.upgrade(alembic_config, "0001_initial")

    engine = sa.create_engine(f"sqlite:///{data_dir / 'haiun.sqlite3'}")
    metadata = sa.MetaData()
    metadata.reflect(engine)
    raw_replays = metadata.tables["raw_replays"]
    canonical_games = metadata.tables["canonical_games"]
    canonical_players = metadata.tables["canonical_players"]
    survivor_replay_id = f"{1:032x}"
    duplicate_replay_id = f"{2:032x}"
    survivor_game_id = f"{3:032x}"
    duplicate_game_id = f"{4:032x}"

    with engine.begin() as connection:
        connection.execute(
            raw_replays.insert(),
            [
                {
                    "id": survivor_replay_id,
                    "source": "majsoul",
                    "external_id": "record-1",
                    "payload": b"first",
                    "sha256": "a" * 64,
                },
                {
                    "id": duplicate_replay_id,
                    "source": "majsoul",
                    "external_id": "record-1",
                    "payload": b"second",
                    "sha256": "b" * 64,
                },
            ],
        )
        connection.execute(
            canonical_games.insert(),
            [
                {
                    "id": survivor_game_id,
                    "raw_replay_id": survivor_replay_id,
                    "schema_version": "1.0.0",
                    "content_hash": "c" * 64,
                    "source": "majsoul",
                    "external_id": "record-1",
                    "game_json": {},
                },
                {
                    "id": duplicate_game_id,
                    "raw_replay_id": duplicate_replay_id,
                    "schema_version": "1.0.0",
                    "content_hash": "d" * 64,
                    "source": "majsoul",
                    "external_id": "record-1",
                    "game_json": {},
                },
            ],
        )
        connection.execute(
            canonical_players.insert(),
            {"game_id": duplicate_game_id, "seat": 0, "name": "orphan candidate"},
        )

    command.upgrade(alembic_config, "head")

    with engine.connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(raw_replays)) == 1
        assert connection.scalar(sa.select(sa.func.count()).select_from(canonical_games)) == 1
        orphan_players = connection.scalar(
            sa.text(
                """
                SELECT COUNT(*)
                FROM canonical_players AS player
                LEFT JOIN canonical_games AS game ON game.id = player.game_id
                WHERE game.id IS NULL
                """
            )
        )
        assert orphan_players == 0

    engine.dispose()


def test_public_access_migration_creates_session_and_submission_tables(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HAIUN_DATA_DIR", str(data_dir))
    alembic_config = Config("backend/alembic.ini")

    command.upgrade(alembic_config, "head")

    engine = sa.create_engine(f"sqlite:///{data_dir / 'haiun.sqlite3'}")
    inspector = sa.inspect(engine)
    assert "admin_sessions" in inspector.get_table_names()
    assert "analysis_submissions" in inspector.get_table_names()
    engine.dispose()


def test_public_access_migration_backfills_existing_analyses(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HAIUN_DATA_DIR", str(data_dir))
    alembic_config = Config("backend/alembic.ini")
    command.upgrade(alembic_config, "0002_cache_raw_replay_identity")

    engine = sa.create_engine(f"sqlite:///{data_dir / 'haiun.sqlite3'}")
    replay_id = f"{1:032x}"
    game_id = f"{2:032x}"
    analysis_id = f"{3:032x}"
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO raw_replays (id, source, external_id, payload, sha256)
                VALUES (:id, 'fixture', 'replay', :payload, :sha256)
                """
            ),
            {"id": replay_id, "payload": b"raw", "sha256": "a" * 64},
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO canonical_games
                    (id, raw_replay_id, schema_version, content_hash, source, external_id, game_json)
                VALUES (:id, :replay_id, '1.0.0', :content_hash, 'fixture', 'game', :game_json)
                """
            ),
            {
                "id": game_id,
                "replay_id": replay_id,
                "content_hash": "b" * 64,
                "game_json": "{}",
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO analyses
                    (id, game_id, algorithm_id, algorithm_version, options_hash, status)
                VALUES (:id, :game_id, 'baseline-v1', '1.0.0', :options_hash, 'completed')
                """
            ),
            {"id": analysis_id, "game_id": game_id, "options_hash": "c" * 64},
        )

    command.upgrade(alembic_config, "head")

    with engine.connect() as connection:
        submission = connection.execute(
            sa.text("SELECT id, analysis_id FROM analysis_submissions")
        ).mappings().one()
    assert submission["id"] == analysis_id
    assert submission["analysis_id"] == analysis_id
    engine.dispose()


def test_app_startup_advances_alembic_before_serving(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("HAIUN_DATA_DIR", str(data_dir))
    alembic_config = Config("backend/alembic.ini")
    command.upgrade(alembic_config, "0002_cache_raw_replay_identity")

    settings = Settings(data_dir=data_dir, config_path=tmp_path / "missing.toml")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200

    command.upgrade(alembic_config, "head")

    engine = sa.create_engine(f"sqlite:///{data_dir / 'haiun.sqlite3'}")
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "0003_public_access"
    engine.dispose()

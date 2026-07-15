from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


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

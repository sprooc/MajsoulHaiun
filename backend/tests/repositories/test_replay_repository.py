from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import Base, create_engine
from app.domain.game import CanonicalGame, Player
from app.domain.rules import RuleSet
from app.repositories.replay_repository import ReplayRepository


@pytest.fixture
async def replay_repository(tmp_path: Path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield ReplayRepository(session)
    await engine.dispose()


async def test_raw_replays_are_deduplicated_by_sha256(replay_repository):
    first = await replay_repository.put_bytes(source="local", external_id="a", payload=b"same")
    second = await replay_repository.put_bytes(source="local", external_id="b", payload=b"same")
    assert first == second


async def test_raw_replays_are_deduplicated_by_source_and_external_id(replay_repository):
    first = await replay_repository.put_bytes(source="majsoul", external_id="record-1", payload=b"first")
    second = await replay_repository.put_bytes(source="majsoul", external_id="record-1", payload=b"second")

    assert first == second
    stored = await replay_repository.get(first)
    assert stored is not None
    assert stored.payload == b"first"


async def test_can_lookup_raw_replay_by_source_and_external_id(replay_repository):
    replay_id = await replay_repository.put_bytes(source="majsoul", external_id="record-1", payload=b"payload")

    stored = await replay_repository.get_by_source_external_id("majsoul", "record-1")

    assert stored is not None
    assert stored.id == replay_id


async def test_concurrent_identity_insert_returns_the_winning_replay():
    winner_id = uuid4()

    class RacingSession:
        def __init__(self):
            self.scalar_results = iter([None, None, SimpleNamespace(id=winner_id)])
            self.rolled_back = False

        async def scalar(self, _statement):
            return next(self.scalar_results)

        def add(self, _model):
            pass

        async def commit(self):
            raise IntegrityError("insert", {}, Exception("unique constraint"))

        async def rollback(self):
            self.rolled_back = True

    session = RacingSession()
    repository = ReplayRepository(session)  # type: ignore[arg-type]

    replay_id = await repository.put_bytes("majsoul", "record-1", b"payload")

    assert replay_id == winner_id
    assert session.rolled_back is True


async def test_raw_bytes_and_canonical_game_are_stored_separately(replay_repository):
    replay_id = await replay_repository.put_bytes(source="local", external_id="g", payload=b"raw")
    game = CanonicalGame(
        source="local",
        external_id="g",
        rules=RuleSet.standard_three_player(),
        players=[Player(seat=seat, name=f"P{seat}") for seat in range(3)],
        rounds=[],
        final_scores=[35000, 35000, 35000],
        final_ranks=[1, 2, 3],
    )
    game_id = await replay_repository.put_canonical_game(replay_id, game)
    stored_raw = await replay_repository.get(replay_id)
    stored_game = await replay_repository.get_game(game_id)
    assert stored_raw is not None and stored_raw.payload == b"raw"
    assert stored_game == game


async def test_replay_can_be_deleted_with_derived_canonical_data(replay_repository):
    replay_id = await replay_repository.put_bytes(source="local", external_id="delete", payload=b"delete")
    game = CanonicalGame(
        source="local",
        external_id="delete",
        rules=RuleSet.standard_three_player(),
        players=[Player(seat=seat, name=f"P{seat}") for seat in range(3)],
        rounds=[],
        final_scores=[35000] * 3,
        final_ranks=[1, 2, 3],
    )
    game_id = await replay_repository.put_canonical_game(replay_id, game)
    assert await replay_repository.delete(replay_id) is True
    assert await replay_repository.get(replay_id) is None
    assert await replay_repository.get_game(game_id) is None

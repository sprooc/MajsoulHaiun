from pathlib import Path

import pytest
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

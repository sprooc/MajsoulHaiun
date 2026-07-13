from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.algorithms.base import LuckAlgorithm
from app.algorithms.registry import AlgorithmRegistry
from app.db import Base, create_engine
from app.domain.analysis import (
    AnalysisOptions,
    EventLuckDetail,
    GameLuckAnalysis,
    PlayerLuckAnalysis,
    RoundLuckAnalysis,
    RoundPlayerLuck,
)
from app.domain.game import CanonicalGame, Player
from app.domain.rules import RuleSet
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.replay_repository import ReplayRepository
from app.services.analysis_service import AnalysisService
from app.models.analysis import AnalysisModel, EventAnalysisModel, PlayerAnalysisModel, RoundAnalysisModel
from app.models.game import CanonicalGameModel
from app.models.replay import RawReplayModel


class CountingAlgorithm(LuckAlgorithm):
    id = "counting"
    version = "1.2.3"
    name_key = "counting.name"
    description_key = "counting.description"

    def __init__(self):
        self.calls = 0

    def supports(self, rules):
        return True

    def analyze(self, game, options):
        self.calls += 1
        round_players = [
            RoundPlayerLuck(
                seat=player.seat,
                raw_delta=0,
                variance=1,
                z_score=0,
                score=50,
                confidence="low",
            )
            for player in game.players
        ]
        return GameLuckAnalysis(
            game_hash=game.content_hash,
            algorithm_id=self.id,
            algorithm_version=self.version,
            options=options,
            players=[
                PlayerLuckAnalysis(
                    seat=player.seat,
                    name=player.name,
                    raw_delta=0,
                    variance=1,
                    z_score=0,
                    score=50,
                    confidence="low",
                    actual_points=0,
                    components={},
                )
                for player in game.players
            ],
            rounds=[
                RoundLuckAnalysis(
                    round_index=0,
                    label="east-1",
                    players=round_players,
                    events=[
                        EventLuckDetail(
                            sequence=0,
                            player=0,
                            component="initial_hand",
                            actual=0,
                            expected=0,
                            delta=0,
                            variance=1,
                            z_score=0,
                            explanation_key="analysis.initialHand",
                        )
                    ],
                )
            ],
        )


@pytest.fixture
async def analysis_context(tmp_path: Path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'analysis.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        replay_repository = ReplayRepository(session)
        replay_id = await replay_repository.put_bytes("fixture", "g", b"raw")
        game = CanonicalGame(
            source="fixture",
            external_id="g",
            rules=RuleSet.standard_three_player(),
            players=[Player(seat=seat, name=f"P{seat}") for seat in range(3)],
            rounds=[],
            final_scores=[35000] * 3,
            final_ranks=[1, 2, 3],
        )
        game_id = await replay_repository.put_canonical_game(replay_id, game)
        algorithm = CountingAlgorithm()
        registry = AlgorithmRegistry()
        registry.register(algorithm)
        service = AnalysisService(replay_repository, AnalysisRepository(session), registry)
        yield service, algorithm, game_id
    await engine.dispose()


async def test_analysis_is_reused_for_same_game_algorithm_version_and_options(analysis_context):
    service, algorithm, game_id = analysis_context
    first = await service.analyze(game_id, algorithm.id, {"eventDetails": True})
    second = await service.analyze(game_id, algorithm.id, {"eventDetails": True})
    assert first.id == second.id
    assert algorithm.calls == 1


async def test_options_are_part_of_cache_key(analysis_context):
    service, algorithm, game_id = analysis_context
    first = await service.analyze(game_id, algorithm.id, {"eventDetails": True})
    second = await service.analyze(game_id, algorithm.id, {"eventDetails": False})
    assert first.id != second.id
    assert algorithm.calls == 2


async def test_missing_game_returns_typed_error(analysis_context):
    service, algorithm, _ = analysis_context
    with pytest.raises(Exception) as error:
        await service.analyze(uuid4(), algorithm.id, {})
    assert error.value.code == "GAME_NOT_FOUND"


async def test_completed_analysis_is_persisted_in_player_round_and_event_layers(analysis_context):
    service, algorithm, game_id = analysis_context

    await service.analyze(game_id, algorithm.id, {"eventDetails": True})
    session = service.analysis_repository.session

    assert await session.scalar(select(func.count()).select_from(PlayerAnalysisModel)) == 3
    assert await session.scalar(select(func.count()).select_from(RoundAnalysisModel)) == 1
    assert await session.scalar(select(func.count()).select_from(EventAnalysisModel)) == 1


async def test_deleting_raw_replay_cascades_through_all_analysis_layers(analysis_context):
    service, algorithm, game_id = analysis_context
    await service.analyze(game_id, algorithm.id, {"eventDetails": True})
    session = service.analysis_repository.session
    replay_id = await session.scalar(select(RawReplayModel.id))

    assert replay_id is not None
    assert await service.replay_repository.delete(replay_id) is True
    for model in (
        CanonicalGameModel,
        AnalysisModel,
        PlayerAnalysisModel,
        RoundAnalysisModel,
        EventAnalysisModel,
    ):
        assert await session.scalar(select(func.count()).select_from(model)) == 0

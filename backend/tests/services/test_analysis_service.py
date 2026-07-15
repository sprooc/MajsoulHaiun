import asyncio
import time
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
from app.models.access import AnalysisSubmissionModel
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
        record_id = "260307-76323960-cf3c-494e-be24-26dd6ba81c98"
        replay_id = await replay_repository.put_bytes("majsoul", record_id, b"raw")
        game = CanonicalGame(
            source="majsoul",
            external_id=record_id,
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
    session = service.analysis_repository.session

    assert first.id != second.id
    assert algorithm.calls == 1
    assert await session.scalar(select(func.count()).select_from(AnalysisModel)) == 1
    assert await session.scalar(select(func.count()).select_from(AnalysisSubmissionModel)) == 2


async def test_analysis_can_be_enqueued_before_processing(analysis_context):
    service, algorithm, game_id = analysis_context

    pending = await service.enqueue(game_id, algorithm.id, {"eventDetails": True})

    assert pending.status == "pending"
    assert pending.result is None
    assert algorithm.calls == 0
    assert pending.game.id == game_id
    assert pending.game.mode == "3p"
    assert pending.game.final_scores == [35000, 35000, 35000]
    assert pending.game.final_ranks == [1, 2, 3]
    assert [player.name for player in pending.game.players] == ["P0", "P1", "P2"]
    assert pending.game.replay_url == (
        "https://game.maj-soul.com/1/?paipu=260307-76323960-cf3c-494e-be24-26dd6ba81c98"
    )

    completed = await service.process(pending.id, {"eventDetails": True})

    assert completed.status == "completed"
    assert completed.result is not None
    assert algorithm.calls == 1


async def test_envelope_normalizes_cached_player_points_to_original_final_scores(analysis_context):
    service, algorithm, game_id = analysis_context

    completed = await service.analyze(game_id, algorithm.id, {"eventDetails": True})

    assert completed.result is not None
    assert [player.actual_points for player in completed.result.players] == [35000, 35000, 35000]


async def test_processing_exposes_analyzing_status_while_algorithm_runs(analysis_context):
    service, algorithm, game_id = analysis_context
    original_analyze = algorithm.analyze

    def slow_analyze(game, options):
        time.sleep(0.1)
        return original_analyze(game, options)

    algorithm.analyze = slow_analyze
    pending = await service.enqueue(game_id, algorithm.id, {"eventDetails": True})

    processing = asyncio.create_task(service.process(pending.id, {"eventDetails": True}))
    await asyncio.sleep(0.02)
    submission = await service.submission_repository.get(pending.id)
    assert submission is not None
    in_progress = await service.analysis_repository.get(submission.analysis_id)

    assert in_progress is not None
    assert in_progress.status == "analyzing"
    await processing


async def test_analyses_are_listed_newest_first_with_game_summary(analysis_context):
    service, algorithm, game_id = analysis_context
    first = await service.enqueue(game_id, algorithm.id, {"eventDetails": True})
    second = await service.enqueue(game_id, algorithm.id, {"eventDetails": False})

    analyses = await service.list_submissions()

    assert [analysis.id for analysis in analyses] == [second.id, first.id]
    assert analyses[0].created_at is not None
    assert analyses[0].game.external_id == "260307-76323960-cf3c-494e-be24-26dd6ba81c98"


async def test_options_are_part_of_cache_key(analysis_context):
    service, algorithm, game_id = analysis_context
    first = await service.analyze(game_id, algorithm.id, {"eventDetails": True})
    second = await service.analyze(game_id, algorithm.id, {"eventDetails": False})
    session = service.analysis_repository.session

    assert first.id != second.id
    assert algorithm.calls == 2
    assert await session.scalar(select(func.count()).select_from(AnalysisModel)) == 2


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
        AnalysisSubmissionModel,
        PlayerAnalysisModel,
        RoundAnalysisModel,
        EventAnalysisModel,
    ):
        assert await session.scalar(select(func.count()).select_from(model)) == 0

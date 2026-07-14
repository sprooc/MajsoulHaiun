import asyncio
import hashlib
import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.algorithms.registry import AlgorithmRegistry
from app.domain.analysis import AnalysisOptions, GameLuckAnalysis
from app.errors import AppError
from app.models.analysis import AnalysisModel
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.replay_repository import CanonicalGameRecord, ReplayRepository


class AnalysisGamePlayer(BaseModel):
    seat: int
    name: str


class AnalysisGameSummary(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=AliasGenerator(serialization_alias=to_camel),
    )

    id: UUID
    mode: Literal["4p", "3p"]
    source: str
    external_id: str
    replay_url: str | None = None
    players: list[AnalysisGamePlayer]
    final_scores: list[int]
    final_ranks: list[int]


class AnalysisEnvelope(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=AliasGenerator(serialization_alias=to_camel),
    )

    id: UUID
    game_id: UUID
    created_at: datetime
    status: str
    game: AnalysisGameSummary
    result: GameLuckAnalysis | None = None
    error_code: str | None = None


class AnalysisService:
    def __init__(
        self,
        replay_repository: ReplayRepository,
        analysis_repository: AnalysisRepository,
        algorithms: AlgorithmRegistry,
    ) -> None:
        self.replay_repository = replay_repository
        self.analysis_repository = analysis_repository
        self.algorithms = algorithms

    @staticmethod
    def options_hash(options: AnalysisOptions) -> str:
        payload = json.dumps(options.model_dump(mode="json", by_alias=True), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _game_summary(game_id: UUID, record: CanonicalGameRecord) -> AnalysisGameSummary:
        replay_url = None
        if record.source == "majsoul":
            replay_url = f"https://game.maj-soul.com/1/?paipu={record.external_id}"
        return AnalysisGameSummary(
            id=game_id,
            mode="4p" if record.game.rules.player_count == 4 else "3p",
            source=record.source,
            external_id=record.external_id,
            replay_url=replay_url,
            players=[AnalysisGamePlayer(seat=player.seat, name=player.name) for player in record.game.players],
            final_scores=record.game.final_scores,
            final_ranks=record.game.final_ranks,
        )

    async def envelope(
        self,
        model: AnalysisModel,
        record: CanonicalGameRecord | None = None,
    ) -> AnalysisEnvelope:
        record = record or await self.replay_repository.get_game_record(model.game_id)
        if record is None:
            raise AppError("GAME_NOT_FOUND", "Canonical game was not found.", status_code=404)
        result = GameLuckAnalysis.model_validate(model.result_json) if model.result_json else None
        if result is not None:
            for player in result.players:
                if 0 <= player.seat < len(record.game.final_scores):
                    player.actual_points = record.game.final_scores[player.seat]
        return AnalysisEnvelope(
            id=model.id,
            game_id=model.game_id,
            created_at=model.created_at,
            status=model.status,
            game=self._game_summary(model.game_id, record),
            result=result,
            error_code=model.error_code,
        )

    async def enqueue(
        self,
        game_id: UUID,
        algorithm_id: str,
        raw_options: AnalysisOptions | dict[str, object],
    ) -> AnalysisEnvelope:
        algorithm = self.algorithms.get(algorithm_id)
        options = raw_options if isinstance(raw_options, AnalysisOptions) else AnalysisOptions.model_validate(raw_options)
        options_hash = self.options_hash(options)
        cached = await self.analysis_repository.find_cached(
            game_id, algorithm.id, algorithm.version, options_hash
        )
        if cached is not None:
            return await self.envelope(cached)

        record = await self.replay_repository.get_game_record(game_id)
        if record is None:
            raise AppError("GAME_NOT_FOUND", "Canonical game was not found.", status_code=404)
        if not algorithm.supports(record.game.rules):
            raise AppError("UNSUPPORTED_GAME_MODE", "Algorithm does not support this game mode.", status_code=422)

        model = AnalysisModel(
            game_id=game_id,
            algorithm_id=algorithm.id,
            algorithm_version=algorithm.version,
            options_hash=options_hash,
            status="pending",
        )
        await self.analysis_repository.add(model)
        return await self.envelope(model, record)

    async def process(
        self,
        analysis_id: UUID,
        raw_options: AnalysisOptions | dict[str, object],
    ) -> AnalysisEnvelope:
        model = await self.analysis_repository.get(analysis_id)
        if model is None:
            raise AppError("ANALYSIS_NOT_FOUND", "Analysis was not found.", status_code=404)
        if model.status != "pending":
            return await self.envelope(model)

        algorithm = self.algorithms.get(model.algorithm_id)
        options = raw_options if isinstance(raw_options, AnalysisOptions) else AnalysisOptions.model_validate(raw_options)
        record = await self.replay_repository.get_game_record(model.game_id)
        if record is None:
            raise AppError("GAME_NOT_FOUND", "Canonical game was not found.", status_code=404)

        try:
            model.status = "analyzing"
            await self.analysis_repository.save(model)
            result = await asyncio.to_thread(algorithm.analyze, record.game, options)
            model.status = "completed"
            await self.analysis_repository.save_result(model, result)
        except AppError as exc:
            model.status = "failed"
            model.error_code = exc.code
            model.error_parameters = exc.parameters
            await self.analysis_repository.save(model)
            raise
        except Exception:
            model.status = "failed"
            model.error_code = "ANALYSIS_FAILED"
            model.error_parameters = {}
            await self.analysis_repository.save(model)
            raise
        return await self.envelope(model, record)

    async def get(self, analysis_id: UUID) -> AnalysisEnvelope:
        model = await self.analysis_repository.get(analysis_id)
        if model is None:
            raise AppError("ANALYSIS_NOT_FOUND", "Analysis was not found.", status_code=404)
        return await self.envelope(model)

    async def list(self) -> list[AnalysisEnvelope]:
        return [await self.envelope(model) for model in await self.analysis_repository.list_all()]

    async def analyze(
        self,
        game_id: UUID,
        algorithm_id: str,
        raw_options: AnalysisOptions | dict[str, object],
    ) -> AnalysisEnvelope:
        queued = await self.enqueue(game_id, algorithm_id, raw_options)
        if queued.status != "pending":
            return queued
        return await self.process(queued.id, raw_options)

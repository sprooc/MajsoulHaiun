import hashlib
import json
from uuid import UUID

from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.algorithms.registry import AlgorithmRegistry
from app.domain.analysis import AnalysisOptions, GameLuckAnalysis
from app.errors import AppError
from app.models.analysis import AnalysisModel
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.replay_repository import ReplayRepository


class AnalysisEnvelope(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=AliasGenerator(serialization_alias=to_camel),
    )

    id: UUID
    status: str
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
    def envelope(model: AnalysisModel) -> AnalysisEnvelope:
        result = GameLuckAnalysis.model_validate(model.result_json) if model.result_json else None
        return AnalysisEnvelope(id=model.id, status=model.status, result=result, error_code=model.error_code)

    async def analyze(
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
            return self.envelope(cached)

        game = await self.replay_repository.get_game(game_id)
        if game is None:
            raise AppError("GAME_NOT_FOUND", "Canonical game was not found.", status_code=404)
        if not algorithm.supports(game.rules):
            raise AppError("UNSUPPORTED_GAME_MODE", "Algorithm does not support this game mode.", status_code=422)

        model = AnalysisModel(
            game_id=game_id,
            algorithm_id=algorithm.id,
            algorithm_version=algorithm.version,
            options_hash=options_hash,
            status="pending",
        )
        await self.analysis_repository.add(model)
        try:
            model.status = "analyzing"
            await self.analysis_repository.save(model)
            result = algorithm.analyze(game, options)
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
        return self.envelope(model)

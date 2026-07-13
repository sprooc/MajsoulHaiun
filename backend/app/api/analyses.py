from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.domain.analysis import AnalysisOptions
from app.errors import AppError
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.replay_repository import ReplayRepository
from app.services.analysis_service import AnalysisEnvelope, AnalysisService


router = APIRouter(prefix="/api", tags=["analyses"])


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=AliasGenerator(validation_alias=to_camel, serialization_alias=to_camel),
    )

    game_id: UUID
    algorithm_id: str
    options: AnalysisOptions = AnalysisOptions()


@router.get("/algorithms")
async def list_algorithms(request: Request) -> list[dict[str, object]]:
    return [
        {
            "id": algorithm.id,
            "version": algorithm.version,
            "nameKey": algorithm.name_key,
            "descriptionKey": algorithm.description_key,
            "supports": ["4p", "3p"],
        }
        for algorithm in request.app.state.algorithm_registry.all()
    ]


@router.post("/analyses", response_model=AnalysisEnvelope, response_model_by_alias=True)
async def create_analysis(request: Request, body: AnalysisRequest) -> AnalysisEnvelope:
    session = request.app.state.session_factory()
    try:
        service = AnalysisService(
            ReplayRepository(session),
            AnalysisRepository(session),
            request.app.state.algorithm_registry,
        )
        return await service.analyze(body.game_id, body.algorithm_id, body.options)
    finally:
        await session.close()


@router.get("/analyses/{analysis_id}", response_model=AnalysisEnvelope, response_model_by_alias=True)
async def get_analysis(request: Request, analysis_id: UUID) -> AnalysisEnvelope:
    session = request.app.state.session_factory()
    try:
        model = await AnalysisRepository(session).get(analysis_id)
        if model is None:
            raise AppError("ANALYSIS_NOT_FOUND", "Analysis was not found.", status_code=404)
        return AnalysisService.envelope(model)
    finally:
        await session.close()

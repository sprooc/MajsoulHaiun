from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.domain.analysis import AnalysisOptions
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.replay_repository import ReplayRepository
from app.services.analysis_service import AnalysisEnvelope, AnalysisService
from app.auth import require_admin


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


async def _process_analysis(request: Request, submission_id: UUID, options: AnalysisOptions) -> None:
    session = request.app.state.session_factory()
    try:
        service = AnalysisService(
            ReplayRepository(session),
            AnalysisRepository(session),
            request.app.state.algorithm_registry,
        )
        await service.process(submission_id, options)
    except Exception:
        return
    finally:
        await session.close()


@router.post("/analyses", response_model=AnalysisEnvelope, response_model_by_alias=True, status_code=202)
async def create_analysis(
    request: Request,
    body: AnalysisRequest,
    background_tasks: BackgroundTasks,
) -> AnalysisEnvelope:
    session = request.app.state.session_factory()
    try:
        service = AnalysisService(
            ReplayRepository(session),
            AnalysisRepository(session),
            request.app.state.algorithm_registry,
        )
        envelope = await service.enqueue(body.game_id, body.algorithm_id, body.options)
        if envelope.status == "pending":
            background_tasks.add_task(_process_analysis, request, envelope.id, body.options)
        return envelope
    finally:
        await session.close()


@router.get("/analyses", response_model=list[AnalysisEnvelope], response_model_by_alias=True)
async def list_analyses(
    request: Request,
    response: Response,
    _admin: None = Depends(require_admin),
) -> list[AnalysisEnvelope]:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie"
    session = request.app.state.session_factory()
    try:
        service = AnalysisService(
            ReplayRepository(session),
            AnalysisRepository(session),
            request.app.state.algorithm_registry,
        )
        return await service.list_submissions()
    finally:
        await session.close()


@router.get("/results/{submission_id}", response_model=AnalysisEnvelope, response_model_by_alias=True)
async def get_analysis(request: Request, submission_id: UUID) -> AnalysisEnvelope:
    session = request.app.state.session_factory()
    try:
        service = AnalysisService(
            ReplayRepository(session),
            AnalysisRepository(session),
            request.app.state.algorithm_registry,
        )
        return await service.get(submission_id)
    finally:
        await session.close()

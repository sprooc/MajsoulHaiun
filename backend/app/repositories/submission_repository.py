from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import AnalysisSubmissionModel
from app.models.analysis import AnalysisModel
from app.models.game import CanonicalGameModel


@dataclass(frozen=True)
class SubmissionSummaryRecord:
    id: UUID
    game_id: UUID
    created_at: datetime
    status: str
    error_code: str | None
    source: str
    external_id: str
    game_json: dict[str, object]


class SubmissionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, analysis_id: UUID) -> AnalysisSubmissionModel:
        model = AnalysisSubmissionModel(analysis_id=analysis_id)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get(self, submission_id: UUID) -> AnalysisSubmissionModel | None:
        return await self.session.get(AnalysisSubmissionModel, submission_id)

    async def list_page(self, offset: int, limit: int) -> list[SubmissionSummaryRecord]:
        rows = (
            await self.session.execute(
                select(
                    AnalysisSubmissionModel.id.label("id"),
                    AnalysisModel.game_id.label("game_id"),
                    AnalysisSubmissionModel.created_at.label("created_at"),
                    AnalysisModel.status.label("status"),
                    AnalysisModel.error_code.label("error_code"),
                    CanonicalGameModel.source.label("source"),
                    CanonicalGameModel.external_id.label("external_id"),
                    CanonicalGameModel.game_json.label("game_json"),
                )
                .select_from(AnalysisSubmissionModel)
                .join(AnalysisModel, AnalysisModel.id == AnalysisSubmissionModel.analysis_id)
                .join(CanonicalGameModel, CanonicalGameModel.id == AnalysisModel.game_id)
                .order_by(
                    AnalysisSubmissionModel.created_at.desc(),
                    AnalysisSubmissionModel.id.desc(),
                )
                .offset(offset)
                .limit(limit + 1)
            )
        ).mappings()
        return [SubmissionSummaryRecord(**row) for row in rows]

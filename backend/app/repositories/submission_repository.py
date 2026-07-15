from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import AnalysisSubmissionModel


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

    async def list_all(self) -> list[AnalysisSubmissionModel]:
        return list(
            await self.session.scalars(
                select(AnalysisSubmissionModel).order_by(
                    AnalysisSubmissionModel.created_at.desc(),
                    AnalysisSubmissionModel.id.desc(),
                )
            )
        )

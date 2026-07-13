from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.analysis import GameLuckAnalysis
from app.models.analysis import AnalysisModel, EventAnalysisModel, PlayerAnalysisModel, RoundAnalysisModel


class AnalysisRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_cached(
        self,
        game_id: UUID,
        algorithm_id: str,
        algorithm_version: str,
        options_hash: str,
    ) -> AnalysisModel | None:
        return await self.session.scalar(
            select(AnalysisModel).where(
                AnalysisModel.game_id == game_id,
                AnalysisModel.algorithm_id == algorithm_id,
                AnalysisModel.algorithm_version == algorithm_version,
                AnalysisModel.options_hash == options_hash,
            )
        )

    async def get(self, analysis_id: UUID) -> AnalysisModel | None:
        return await self.session.get(AnalysisModel, analysis_id)

    async def add(self, model: AnalysisModel) -> AnalysisModel:
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def save(self, model: AnalysisModel) -> AnalysisModel:
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def save_result(self, model: AnalysisModel, result: GameLuckAnalysis) -> AnalysisModel:
        model.result_json = result.model_dump(mode="json", by_alias=True)
        self.session.add_all(
            [
                PlayerAnalysisModel(
                    analysis_id=model.id,
                    seat=player.seat,
                    score=player.score,
                    z_score=player.z_score,
                    result_json=player.model_dump(mode="json", by_alias=True),
                )
                for player in result.players
            ]
        )
        for round_result in result.rounds:
            round_model = RoundAnalysisModel(
                analysis_id=model.id,
                round_index=round_result.round_index,
                result_json=round_result.model_dump(mode="json", by_alias=True),
            )
            self.session.add(round_model)
            await self.session.flush()
            self.session.add_all(
                [
                    EventAnalysisModel(
                        round_analysis_id=round_model.id,
                        sequence=event.sequence,
                        component=event.component,
                        result_json=event.model_dump(mode="json", by_alias=True),
                        explanation_key=event.explanation_key,
                    )
                    for event in round_result.events
                ]
            )
        await self.session.commit()
        await self.session.refresh(model)
        return model

import hashlib
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.game import CanonicalGame
from app.models.game import CanonicalEventModel, CanonicalGameModel, CanonicalPlayerModel, CanonicalRoundModel
from app.models.replay import RawReplayModel


@dataclass(frozen=True)
class RawReplayRecord:
    id: UUID
    source: str
    external_id: str
    payload: bytes
    sha256: str
    filename: str | None
    content_type: str | None


class ReplayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def put_bytes(
        self,
        source: str,
        external_id: str,
        payload: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> UUID:
        existing = await self.session.scalar(
            select(RawReplayModel).where(
                RawReplayModel.source == source,
                RawReplayModel.external_id == external_id,
            )
        )
        if existing:
            return existing.id
        digest = hashlib.sha256(payload).hexdigest()
        existing = await self.session.scalar(select(RawReplayModel).where(RawReplayModel.sha256 == digest))
        if existing:
            return existing.id
        model = RawReplayModel(
            source=source,
            external_id=external_id,
            payload=payload,
            sha256=digest,
            filename=filename,
            content_type=content_type,
        )
        self.session.add(model)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(RawReplayModel).where(
                    RawReplayModel.source == source,
                    RawReplayModel.external_id == external_id,
                )
            )
            if existing is None:
                existing = await self.session.scalar(select(RawReplayModel).where(RawReplayModel.sha256 == digest))
            if existing is None:
                raise
            return existing.id
        return model.id

    async def get(self, replay_id: UUID) -> RawReplayRecord | None:
        model = await self.session.get(RawReplayModel, replay_id)
        if model is None:
            return None
        return RawReplayRecord(
            id=model.id,
            source=model.source,
            external_id=model.external_id,
            payload=model.payload,
            sha256=model.sha256,
            filename=model.filename,
            content_type=model.content_type,
        )

    async def get_by_sha256(self, sha256: str) -> RawReplayRecord | None:
        model = await self.session.scalar(select(RawReplayModel).where(RawReplayModel.sha256 == sha256))
        return await self.get(model.id) if model else None

    async def get_by_source_external_id(self, source: str, external_id: str) -> RawReplayRecord | None:
        model = await self.session.scalar(
            select(RawReplayModel).where(
                RawReplayModel.source == source,
                RawReplayModel.external_id == external_id,
            )
        )
        return await self.get(model.id) if model else None

    async def put_canonical_game(self, replay_id: UUID, game: CanonicalGame) -> UUID:
        existing = await self.session.scalar(
            select(CanonicalGameModel).where(
                CanonicalGameModel.raw_replay_id == replay_id,
                CanonicalGameModel.schema_version == game.schema_version,
            )
        )
        if existing:
            return existing.id
        model = CanonicalGameModel(
            raw_replay_id=replay_id,
            schema_version=game.schema_version,
            content_hash=game.content_hash,
            source=game.source,
            external_id=game.external_id,
            game_json=game.model_dump(mode="json"),
        )
        for player in game.players:
            model.players.append(
                CanonicalPlayerModel(seat=player.seat, name=player.name, external_id=player.external_id)
            )
        for round_ in game.rounds:
            round_model = CanonicalRoundModel(round_index=round_.index, round_json=round_.model_dump(mode="json"))
            for event in round_.events:
                round_model.events.append(
                    CanonicalEventModel(
                        sequence=event.sequence,
                        event_type=event.event_type,
                        event_json=event.model_dump(mode="json"),
                        diagnostic=event.raw_type if event.event_type == "unknown" else None,
                    )
                )
            model.rounds.append(round_model)
        self.session.add(model)
        await self.session.commit()
        return model.id

    async def get_game(self, game_id: UUID) -> CanonicalGame | None:
        model = await self.session.get(CanonicalGameModel, game_id)
        return CanonicalGame.model_validate(model.game_json) if model else None

    async def get_game_model(self, game_id: UUID) -> CanonicalGameModel | None:
        return await self.session.scalar(
            select(CanonicalGameModel)
            .where(CanonicalGameModel.id == game_id)
            .options(selectinload(CanonicalGameModel.analyses))
        )

    async def delete(self, replay_id: UUID) -> bool:
        result = await self.session.execute(delete(RawReplayModel).where(RawReplayModel.id == replay_id))
        await self.session.commit()
        return bool(result.rowcount)

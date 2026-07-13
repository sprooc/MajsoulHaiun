from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class CanonicalGameModel(Base):
    __tablename__ = "canonical_games"
    __table_args__ = (
        UniqueConstraint("raw_replay_id", "schema_version", name="uq_canonical_game_replay_schema"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    raw_replay_id: Mapped[UUID] = mapped_column(ForeignKey("raw_replays.id", ondelete="CASCADE"), index=True)
    schema_version: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(256), index=True)
    game_json: Mapped[dict] = mapped_column(JSON)

    raw_replay = relationship("RawReplayModel", back_populates="games")
    players = relationship("CanonicalPlayerModel", cascade="all, delete-orphan")
    rounds = relationship("CanonicalRoundModel", cascade="all, delete-orphan")
    analyses = relationship("AnalysisModel", cascade="all, delete-orphan")


class CanonicalPlayerModel(Base):
    __tablename__ = "canonical_players"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    game_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_games.id", ondelete="CASCADE"), index=True)
    seat: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(256))
    external_id: Mapped[str | None] = mapped_column(String(256))


class CanonicalRoundModel(Base):
    __tablename__ = "canonical_rounds"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    game_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_games.id", ondelete="CASCADE"), index=True)
    round_index: Mapped[int] = mapped_column(Integer)
    round_json: Mapped[dict] = mapped_column(JSON)
    events = relationship("CanonicalEventModel", cascade="all, delete-orphan")


class CanonicalEventModel(Base):
    __tablename__ = "canonical_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("canonical_rounds.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    event_json: Mapped[dict] = mapped_column(JSON)
    diagnostic: Mapped[str | None] = mapped_column(Text)

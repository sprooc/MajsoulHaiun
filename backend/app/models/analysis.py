from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AnalysisModel(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "algorithm_id",
            "algorithm_version",
            "options_hash",
            name="uq_analysis_cache_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    game_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_games.id", ondelete="CASCADE"), index=True)
    algorithm_id: Mapped[str] = mapped_column(String(128))
    algorithm_version: Mapped[str] = mapped_column(String(64))
    options_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    result_json: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_parameters: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    players = relationship("PlayerAnalysisModel", cascade="all, delete-orphan")
    rounds = relationship("RoundAnalysisModel", cascade="all, delete-orphan")


class PlayerAnalysisModel(Base):
    __tablename__ = "player_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    seat: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    z_score: Mapped[float] = mapped_column(Float)
    result_json: Mapped[dict] = mapped_column(JSON)


class RoundAnalysisModel(Base):
    __tablename__ = "round_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    round_index: Mapped[int] = mapped_column(Integer)
    result_json: Mapped[dict] = mapped_column(JSON)
    events = relationship("EventAnalysisModel", cascade="all, delete-orphan")


class EventAnalysisModel(Base):
    __tablename__ = "event_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    round_analysis_id: Mapped[int] = mapped_column(ForeignKey("round_analyses.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    component: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict] = mapped_column(JSON)
    explanation_key: Mapped[str | None] = mapped_column(Text)

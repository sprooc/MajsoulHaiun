from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RawReplayModel(Base):
    __tablename__ = "raw_replays"
    __table_args__ = (UniqueConstraint("sha256", name="uq_raw_replays_sha256"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(256), index=True)
    filename: Mapped[str | None] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    games = relationship("CanonicalGameModel", back_populates="raw_replay", cascade="all, delete-orphan")

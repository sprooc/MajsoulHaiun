"""Add public analysis submissions and administrator sessions."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_public_access"
down_revision: str | None = "0002_cache_raw_replay_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_admin_sessions_token_hash", "admin_sessions", ["token_hash"], unique=True)
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])

    op.create_table(
        "analysis_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_submissions_analysis_id",
        "analysis_submissions",
        ["analysis_id"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO analysis_submissions (id, analysis_id, created_at)
            SELECT id, id, created_at FROM analyses
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_submissions_analysis_id", table_name="analysis_submissions")
    op.drop_table("analysis_submissions")
    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_token_hash", table_name="admin_sessions")
    op.drop_table("admin_sessions")

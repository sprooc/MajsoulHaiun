"""Initial Haiun persistence schema."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_replays",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("filename", sa.String(512)),
        sa.Column("content_type", sa.String(128)),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256", name="uq_raw_replays_sha256"),
    )
    op.create_table(
        "canonical_games",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("raw_replay_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("game_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["raw_replay_id"], ["raw_replays.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_replay_id", "schema_version", name="uq_canonical_game_replay_schema"),
    )
    op.create_table(
        "canonical_players",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.Uuid(), sa.ForeignKey("canonical_games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seat", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("external_id", sa.String(256)),
    )
    op.create_table(
        "canonical_rounds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.Uuid(), sa.ForeignKey("canonical_games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("round_json", sa.JSON(), nullable=False),
    )
    op.create_table(
        "canonical_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("canonical_rounds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_json", sa.JSON(), nullable=False),
        sa.Column("diagnostic", sa.Text()),
    )
    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), sa.ForeignKey("canonical_games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("algorithm_id", sa.String(128), nullable=False),
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        sa.Column("options_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error_code", sa.String(128)),
        sa.Column("error_parameters", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "algorithm_id", "algorithm_version", "options_hash", name="uq_analysis_cache_key"),
    )
    op.create_table(
        "player_analyses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("analysis_id", sa.Uuid(), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seat", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("z_score", sa.Float(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
    )
    op.create_table(
        "round_analyses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("analysis_id", sa.Uuid(), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
    )
    op.create_table(
        "event_analyses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("round_analysis_id", sa.Integer(), sa.ForeignKey("round_analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("component", sa.String(64), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("explanation_key", sa.Text()),
    )


def downgrade() -> None:
    for table in (
        "event_analyses",
        "round_analyses",
        "player_analyses",
        "analyses",
        "canonical_events",
        "canonical_rounds",
        "canonical_players",
        "canonical_games",
        "raw_replays",
    ):
        op.drop_table(table)

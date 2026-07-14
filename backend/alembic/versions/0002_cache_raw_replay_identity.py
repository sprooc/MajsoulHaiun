"""Cache raw replays by source and external identity."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_cache_raw_replay_identity"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _remove_duplicate_identities() -> None:
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            """
            SELECT source, external_id
            FROM raw_replays
            GROUP BY source, external_id
            HAVING COUNT(*) > 1
            """
        )
    ).mappings()
    for duplicate in duplicates:
        replay_ids = connection.execute(
            sa.text(
                """
                SELECT id
                FROM raw_replays
                WHERE source = :source AND external_id = :external_id
                ORDER BY created_at, id
                """
            ),
            duplicate,
        ).scalars().all()
        survivor = replay_ids[0]
        for replay_id in replay_ids[1:]:
            games = connection.execute(
                sa.text(
                    "SELECT id, schema_version FROM canonical_games WHERE raw_replay_id = :replay_id"
                ),
                {"replay_id": replay_id},
            ).mappings()
            for game in games:
                existing_game = connection.execute(
                    sa.text(
                        """
                        SELECT id FROM canonical_games
                        WHERE raw_replay_id = :survivor AND schema_version = :schema_version
                        """
                    ),
                    {"survivor": survivor, "schema_version": game["schema_version"]},
                ).scalar_one_or_none()
                if existing_game is None:
                    connection.execute(
                        sa.text("UPDATE canonical_games SET raw_replay_id = :survivor WHERE id = :game_id"),
                        {"survivor": survivor, "game_id": game["id"]},
                    )
                else:
                    connection.execute(
                        sa.text("DELETE FROM canonical_games WHERE id = :game_id"),
                        {"game_id": game["id"]},
                    )
            connection.execute(
                sa.text("DELETE FROM raw_replays WHERE id = :replay_id"),
                {"replay_id": replay_id},
            )


def upgrade() -> None:
    _remove_duplicate_identities()
    with op.batch_alter_table("raw_replays") as batch_op:
        batch_op.create_unique_constraint(
            "uq_raw_replays_source_external",
            ["source", "external_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("raw_replays") as batch_op:
        batch_op.drop_constraint("uq_raw_replays_source_external", type_="unique")

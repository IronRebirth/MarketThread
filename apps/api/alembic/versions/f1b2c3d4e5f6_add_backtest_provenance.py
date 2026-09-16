"""Add persisted backtest provenance."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1b2c3d4e5f6"
down_revision: str | None = "e7a1b3c4d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create persisted backtest provenance records."""

    op.create_table(
        "backtest_provenance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("backtest_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("ruleset_version", sa.String(length=64), nullable=False),
        sa.Column("input_ids", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column(
            "invalidation_conditions",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["backtest_id"],
            ["backtest_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "backtest_id",
            name="uq_backtest_provenance_backtest_id",
        ),
    )

    op.create_index(
        "ix_backtest_provenance_backtest_id",
        "backtest_provenance",
        ["backtest_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove persisted backtest provenance."""

    op.drop_index(
        "ix_backtest_provenance_backtest_id",
        table_name="backtest_provenance",
    )
    op.drop_table("backtest_provenance")

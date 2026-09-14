"""Create persisted market signals table."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7c82d1f4a9b6"
down_revision: str | None = "4f27a1c9d6e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable historical signal snapshots."""

    op.create_table(
        "signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("strength", sa.String(length=32), nullable=False),
        sa.Column("opportunity", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("time_horizon", sa.String(length=32), nullable=False),
        sa.Column("supporting_factors", sa.JSON(), nullable=False),
        sa.Column("contradicting_factors", sa.JSON(), nullable=False),
        sa.Column("evidence_article_ids", sa.JSON(), nullable=False),
        sa.Column("invalidation_conditions", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_signals_event_id",
        "signals",
        ["event_id"],
    )
    op.create_index(
        "ix_signals_instrument_id",
        "signals",
        ["instrument_id"],
    )
    op.create_index(
        "ix_signals_ticker",
        "signals",
        ["ticker"],
    )
    op.create_index(
        "ix_signals_created_at",
        "signals",
        ["created_at"],
    )
    op.create_index(
        "ix_signals_strength",
        "signals",
        ["strength"],
    )
    op.create_index(
        "ix_signals_opportunity",
        "signals",
        ["opportunity"],
    )


def downgrade() -> None:
    """Drop persisted historical signal snapshots."""

    op.drop_index(
        "ix_signals_opportunity",
        table_name="signals",
    )
    op.drop_index(
        "ix_signals_strength",
        table_name="signals",
    )
    op.drop_index(
        "ix_signals_created_at",
        table_name="signals",
    )
    op.drop_index(
        "ix_signals_ticker",
        table_name="signals",
    )
    op.drop_index(
        "ix_signals_instrument_id",
        table_name="signals",
    )
    op.drop_index(
        "ix_signals_event_id",
        table_name="signals",
    )
    op.drop_table("signals")

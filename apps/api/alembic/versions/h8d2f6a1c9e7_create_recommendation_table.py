"""create recommendation table

Revision ID: h8d2f6a1c9e7
Revises: g7c1e4f9b2d5
Create Date: 2026-09-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h8d2f6a1c9e7"
down_revision: str | Sequence[str] | None = "g7c1e4f9b2d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("signal_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("signal_direction", sa.String(length=32), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("confidence_level", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("time_horizon", sa.String(length=32), nullable=False),
        sa.Column("supporting_factors", sa.JSON(), nullable=False),
        sa.Column("contradicting_factors", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("invalidation_conditions", sa.JSON(), nullable=False),
        sa.Column("evidence_article_ids", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["signal_id"],
            ["signals.id"],
            name="fk_recommendations_signal_id_signals",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "signal_id",
            name="uq_recommendations_signal",
        ),
    )

    op.create_index(
        "ix_recommendations_signal_id",
        "recommendations",
        ["signal_id"],
    )
    op.create_index(
        "ix_recommendations_event_id",
        "recommendations",
        ["event_id"],
    )
    op.create_index(
        "ix_recommendations_company_name",
        "recommendations",
        ["company_name"],
    )
    op.create_index(
        "ix_recommendations_ticker",
        "recommendations",
        ["ticker"],
    )
    op.create_index(
        "ix_recommendations_created_at",
        "recommendations",
        ["created_at"],
    )
    op.create_index(
        "ix_recommendations_state",
        "recommendations",
        ["state"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_recommendations_state",
        table_name="recommendations",
    )
    op.drop_index(
        "ix_recommendations_created_at",
        table_name="recommendations",
    )
    op.drop_index(
        "ix_recommendations_ticker",
        table_name="recommendations",
    )
    op.drop_index(
        "ix_recommendations_company_name",
        table_name="recommendations",
    )
    op.drop_index(
        "ix_recommendations_event_id",
        table_name="recommendations",
    )
    op.drop_index(
        "ix_recommendations_signal_id",
        table_name="recommendations",
    )
    op.drop_constraint(
        "fk_recommendations_signal_id_signals",
        "recommendations",
        type_="foreignkey",
    )
    op.drop_table("recommendations")

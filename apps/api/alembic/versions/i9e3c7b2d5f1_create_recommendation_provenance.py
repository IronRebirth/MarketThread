"""create recommendation provenance

Revision ID: i9e3c7b2d5f1
Revises: h8d2f6a1c9e7
Create Date: 2026-09-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "i9e3c7b2d5f1"
down_revision: str | Sequence[str] | None = "h8d2f6a1c9e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "recommendation_provenance",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recommendation_id", sa.UUID(), nullable=False),
        sa.Column("signal_id", sa.UUID(), nullable=False),
        sa.Column("market_impact_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ruleset_version", sa.String(length=64), nullable=False),
        sa.Column("input_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_article_ids", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("invalidation_conditions", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendations.id"],
            name="fk_recommendation_provenance_recommendation_id_recommendations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recommendation_id",
            name="uq_recommendation_provenance_recommendation",
        ),
    )

    op.create_index(
        "ix_recommendation_provenance_recommendation_id",
        "recommendation_provenance",
        ["recommendation_id"],
    )
    op.create_index(
        "ix_recommendation_provenance_signal_id",
        "recommendation_provenance",
        ["signal_id"],
    )
    op.create_index(
        "ix_recommendation_provenance_market_impact_id",
        "recommendation_provenance",
        ["market_impact_id"],
    )
    op.create_index(
        "ix_recommendation_provenance_event_id",
        "recommendation_provenance",
        ["event_id"],
    )
    op.create_index(
        "ix_recommendation_provenance_created_at",
        "recommendation_provenance",
        ["created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_recommendation_provenance_created_at",
        table_name="recommendation_provenance",
    )
    op.drop_index(
        "ix_recommendation_provenance_event_id",
        table_name="recommendation_provenance",
    )
    op.drop_index(
        "ix_recommendation_provenance_market_impact_id",
        table_name="recommendation_provenance",
    )
    op.drop_index(
        "ix_recommendation_provenance_signal_id",
        table_name="recommendation_provenance",
    )
    op.drop_index(
        "ix_recommendation_provenance_recommendation_id",
        table_name="recommendation_provenance",
    )
    op.drop_constraint(
        "fk_recommendation_provenance_recommendation_id_recommendations",
        "recommendation_provenance",
        type_="foreignkey",
    )
    op.drop_table("recommendation_provenance")

"""create market impact table

Revision ID: e6f2a9b4c7d1
Revises: d4e8f1a7c2b3
Create Date: 2026-09-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6f2a9b4c7d1"
down_revision: str | Sequence[str] | None = "d4e8f1a7c2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "market_impacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_impact_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("impact_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("factor", sa.String(length=64), nullable=False),
        sa.Column("time_horizon", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_article_ids", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_impact_id"],
            ["company_impacts.id"],
            name="fk_market_impacts_company_impact_id_company_impacts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_market_impacts_event_id_events",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_impact_id",
            name="uq_market_impacts_company_impact",
        ),
    )

    op.create_index(
        "ix_market_impacts_company_impact_id",
        "market_impacts",
        ["company_impact_id"],
    )
    op.create_index(
        "ix_market_impacts_event_id",
        "market_impacts",
        ["event_id"],
    )
    op.create_index(
        "ix_market_impacts_company_name",
        "market_impacts",
        ["company_name"],
    )
    op.create_index(
        "ix_market_impacts_impact_type",
        "market_impacts",
        ["impact_type"],
    )
    op.create_index(
        "ix_market_impacts_direction",
        "market_impacts",
        ["direction"],
    )
    op.create_index(
        "ix_market_impacts_factor",
        "market_impacts",
        ["factor"],
    )
    op.create_index(
        "ix_market_impacts_time_horizon",
        "market_impacts",
        ["time_horizon"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_market_impacts_time_horizon",
        table_name="market_impacts",
    )
    op.drop_index(
        "ix_market_impacts_factor",
        table_name="market_impacts",
    )
    op.drop_index(
        "ix_market_impacts_direction",
        table_name="market_impacts",
    )
    op.drop_index(
        "ix_market_impacts_impact_type",
        table_name="market_impacts",
    )
    op.drop_index(
        "ix_market_impacts_company_name",
        table_name="market_impacts",
    )
    op.drop_index(
        "ix_market_impacts_event_id",
        table_name="market_impacts",
    )
    op.drop_index(
        "ix_market_impacts_company_impact_id",
        table_name="market_impacts",
    )
    op.drop_table("market_impacts")

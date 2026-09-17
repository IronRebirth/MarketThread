"""create company impact table

Revision ID: d4e8f1a7c2b3
Revises: c8d3e2f1a7b4
Create Date: 2026-09-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e8f1a7c2b3"
down_revision: str | Sequence[str] | None = "c8d3e2f1a7b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "company_impacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column("impact_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("mechanism", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_article_ids", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_company_impacts_event_id_events",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "company_name",
            "impact_type",
            name="uq_company_impacts_event_company_type",
        ),
    )

    op.create_index(
        "ix_company_impacts_event_id",
        "company_impacts",
        ["event_id"],
    )
    op.create_index(
        "ix_company_impacts_company_name",
        "company_impacts",
        ["company_name"],
    )
    op.create_index(
        "ix_company_impacts_ticker",
        "company_impacts",
        ["ticker"],
    )
    op.create_index(
        "ix_company_impacts_impact_type",
        "company_impacts",
        ["impact_type"],
    )
    op.create_index(
        "ix_company_impacts_direction",
        "company_impacts",
        ["direction"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_company_impacts_direction", table_name="company_impacts")
    op.drop_index("ix_company_impacts_impact_type", table_name="company_impacts")
    op.drop_index("ix_company_impacts_ticker", table_name="company_impacts")
    op.drop_index("ix_company_impacts_company_name", table_name="company_impacts")
    op.drop_index("ix_company_impacts_event_id", table_name="company_impacts")
    op.drop_table("company_impacts")

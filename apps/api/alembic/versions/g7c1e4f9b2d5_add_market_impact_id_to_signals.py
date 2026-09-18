"""add market impact id to signals

Revision ID: g7c1e4f9b2d5
Revises: f3b7c1d9e5a2
Create Date: 2026-09-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g7c1e4f9b2d5"
down_revision: str | Sequence[str] | None = "f3b7c1d9e5a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "signals",
        sa.Column("market_impact_id", sa.UUID(), nullable=True),
    )

    op.create_foreign_key(
        "fk_signals_market_impact_id_market_impacts",
        "signals",
        "market_impacts",
        ["market_impact_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_signals_market_impact_id",
        "signals",
        ["market_impact_id"],
    )

    op.create_unique_constraint(
        "uq_signals_market_impact",
        "signals",
        ["market_impact_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_signals_market_impact",
        "signals",
        type_="unique",
    )
    op.drop_index(
        "ix_signals_market_impact_id",
        table_name="signals",
    )
    op.drop_constraint(
        "fk_signals_market_impact_id_market_impacts",
        "signals",
        type_="foreignkey",
    )
    op.drop_column(
        "signals",
        "market_impact_id",
    )

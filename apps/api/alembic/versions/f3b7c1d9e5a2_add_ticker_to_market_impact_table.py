"""add ticker to market impact table

Revision ID: f3b7c1d9e5a2
Revises: e6f2a9b4c7d1
Create Date: 2026-09-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3b7c1d9e5a2"
down_revision: str | Sequence[str] | None = "e6f2a9b4c7d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "market_impacts",
        sa.Column("ticker", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_market_impacts_ticker",
        "market_impacts",
        ["ticker"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_market_impacts_ticker",
        table_name="market_impacts",
    )
    op.drop_column(
        "market_impacts",
        "ticker",
    )

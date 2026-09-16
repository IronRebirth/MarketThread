"""Add per-horizon market-data quality metadata to backtest runs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7a1b3c4d5f6"
down_revision: str | None = "d6f4a2b8c1e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add persisted per-horizon market-data quality metadata."""
    op.add_column(
        "backtest_runs",
        sa.Column(
            "market_data_horizon_quality",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove persisted per-horizon market-data quality metadata."""
    op.drop_column(
        "backtest_runs",
        "market_data_horizon_quality",
    )

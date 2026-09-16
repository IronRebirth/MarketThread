"""Add market-data quality metadata to backtest runs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d6f4a2b8c1e9"
down_revision: str | None = "b7e9c3d4a1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add server-side market-data coverage metadata."""

    op.add_column(
        "backtest_runs",
        sa.Column(
            "market_data_expected_count",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "backtest_runs",
        sa.Column(
            "market_data_resolved_count",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "backtest_runs",
        sa.Column(
            "market_data_coverage_ratio",
            sa.Float(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove server-side market-data coverage metadata."""

    op.drop_column(
        "backtest_runs",
        "market_data_coverage_ratio",
    )

    op.drop_column(
        "backtest_runs",
        "market_data_resolved_count",
    )

    op.drop_column(
        "backtest_runs",
        "market_data_expected_count",
    )

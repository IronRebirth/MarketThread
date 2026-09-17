"""Add persisted backtest run configuration."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2c4e6f8b0d1"
down_revision: str | None = "f1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add an optional configuration snapshot to persisted backtest runs."""

    op.add_column(
        "backtest_runs",
        sa.Column(
            "configuration",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove the persisted backtest run configuration."""

    op.drop_column(
        "backtest_runs",
        "configuration",
    )

"""Add market-data ingestion uniqueness constraints."""

from collections.abc import Sequence

from alembic import op

revision: str = "b7e9c3d4a1f2"
down_revision: str | None = "7c82d1f4a9b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add natural-key constraints for idempotent market-data ingestion."""

    op.create_unique_constraint(
        "uq_market_quotes_instrument_timestamp_source",
        "market_quotes",
        ["instrument_id", "timestamp", "source"],
    )

    op.create_unique_constraint(
        "uq_market_bars_instrument_timestamp_source",
        "market_bars",
        ["instrument_id", "timestamp", "source"],
    )


def downgrade() -> None:
    """Remove market-data ingestion uniqueness constraints."""

    op.drop_constraint(
        "uq_market_bars_instrument_timestamp_source",
        "market_bars",
        type_="unique",
    )

    op.drop_constraint(
        "uq_market_quotes_instrument_timestamp_source",
        "market_quotes",
        type_="unique",
    )

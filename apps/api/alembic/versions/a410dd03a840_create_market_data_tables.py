"""Create market data tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a410dd03a840"
down_revision: str | None = "c9915ebc9db7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the market data tables."""

    op.create_table(
        "instruments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("exchange", sa.String(length=64), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol",
            "exchange",
            name="uq_instruments_symbol_exchange",
        ),
    )

    op.create_table(
        "market_quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "instrument_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "price",
            sa.Numeric(20, 8),
            nullable=False,
        ),
        sa.Column(
            "bid",
            sa.Numeric(20, 8),
            nullable=True,
        ),
        sa.Column(
            "ask",
            sa.Numeric(20, 8),
            nullable=True,
        ),
        sa.Column(
            "volume",
            sa.Numeric(24, 8),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_market_quotes_instrument_id",
        "market_quotes",
        ["instrument_id"],
    )
    op.create_index(
        "ix_market_quotes_timestamp",
        "market_quotes",
        ["timestamp"],
    )

    op.create_table(
        "market_bars",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "instrument_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "open",
            sa.Numeric(20, 8),
            nullable=False,
        ),
        sa.Column(
            "high",
            sa.Numeric(20, 8),
            nullable=False,
        ),
        sa.Column(
            "low",
            sa.Numeric(20, 8),
            nullable=False,
        ),
        sa.Column(
            "close",
            sa.Numeric(20, 8),
            nullable=False,
        ),
        sa.Column(
            "volume",
            sa.Numeric(24, 8),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_market_bars_instrument_id",
        "market_bars",
        ["instrument_id"],
    )
    op.create_index(
        "ix_market_bars_timestamp",
        "market_bars",
        ["timestamp"],
    )


def downgrade() -> None:
    """Drop the market data tables."""

    op.drop_index(
        "ix_market_bars_timestamp",
        table_name="market_bars",
    )
    op.drop_index(
        "ix_market_bars_instrument_id",
        table_name="market_bars",
    )
    op.drop_table("market_bars")

    op.drop_index(
        "ix_market_quotes_timestamp",
        table_name="market_quotes",
    )
    op.drop_index(
        "ix_market_quotes_instrument_id",
        table_name="market_quotes",
    )
    op.drop_table("market_quotes")

    op.drop_table("instruments")

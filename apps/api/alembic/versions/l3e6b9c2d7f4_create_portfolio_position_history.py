"""Create portfolio position history table.

Revision ID: l3e6b9c2d7f4
Revises: k2d5f8a1c4e7
Create Date: 2026-09-18
"""

import sqlalchemy as sa

from alembic import op

revision = "l3e6b9c2d7f4"
down_revision = "k2d5f8a1c4e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the append-only portfolio position history table."""

    op.create_table(
        "portfolio_position_history",
        sa.Column(
            "sequence_id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "portfolio_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "instrument_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(24, 8),
            nullable=False,
        ),
        sa.Column(
            "average_cost",
            sa.Numeric(20, 8),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("sequence_id"),
        sa.UniqueConstraint("id"),
    )

    op.create_index(
        "ix_portfolio_position_history_portfolio_id",
        "portfolio_position_history",
        ["portfolio_id"],
        unique=False,
    )

    op.create_index(
        "ix_portfolio_position_history_instrument_id",
        "portfolio_position_history",
        ["instrument_id"],
        unique=False,
    )

    op.create_index(
        "ix_portfolio_position_history_recorded_at",
        "portfolio_position_history",
        ["recorded_at"],
        unique=False,
    )

    op.create_index(
        "ix_portfolio_position_history_portfolio_instrument_sequence",
        "portfolio_position_history",
        ["portfolio_id", "instrument_id", "sequence_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the portfolio position history table."""

    op.drop_index(
        "ix_portfolio_position_history_portfolio_instrument_sequence",
        table_name="portfolio_position_history",
    )
    op.drop_index(
        "ix_portfolio_position_history_recorded_at",
        table_name="portfolio_position_history",
    )
    op.drop_index(
        "ix_portfolio_position_history_instrument_id",
        table_name="portfolio_position_history",
    )
    op.drop_index(
        "ix_portfolio_position_history_portfolio_id",
        table_name="portfolio_position_history",
    )
    op.drop_table("portfolio_position_history")

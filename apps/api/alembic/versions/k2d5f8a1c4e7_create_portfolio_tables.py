"""Create portfolio tables.

Revision ID: k2d5f8a1c4e7
Revises: j0f4a8c3b6d2
Create Date: 2026-09-18
"""

import sqlalchemy as sa

from alembic import op

revision = "k2d5f8a1c4e7"
down_revision = "j0f4a8c3b6d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create portfolio and portfolio-position tables."""

    op.create_table(
        "portfolios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "name",
            name="uq_portfolios_user_name",
        ),
    )

    op.create_index(
        "ix_portfolios_user_id",
        "portfolios",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "portfolio_positions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=False),
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
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_id",
            "instrument_id",
            name="uq_portfolio_positions_portfolio_instrument",
        ),
    )

    op.create_index(
        "ix_portfolio_positions_portfolio_id",
        "portfolio_positions",
        ["portfolio_id"],
        unique=False,
    )

    op.create_index(
        "ix_portfolio_positions_instrument_id",
        "portfolio_positions",
        ["instrument_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop portfolio tables."""

    op.drop_index(
        "ix_portfolio_positions_instrument_id",
        table_name="portfolio_positions",
    )
    op.drop_index(
        "ix_portfolio_positions_portfolio_id",
        table_name="portfolio_positions",
    )
    op.drop_table("portfolio_positions")

    op.drop_index(
        "ix_portfolios_user_id",
        table_name="portfolios",
    )
    op.drop_table("portfolios")

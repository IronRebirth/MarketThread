"""create portfolio cash flow history

Revision ID: n5h8k3m1d7p9
Revises: m4f7c2d9e1a6
Create Date: 2026-09-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "n5h8k3m1d7p9"
down_revision: str | None = "m4f7c2d9e1a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the append-only portfolio cash-flow ledger."""

    op.create_table(
        "portfolio_cash_flow_history",
        sa.Column(
            "sequence_id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "amount",
            sa.Numeric(20, 8),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_portfolio_cash_flow_positive_amount",
        ),
        sa.CheckConstraint(
            "event_type IN ('deposit', 'withdrawal')",
            name="ck_portfolio_cash_flow_event_type",
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
        "ix_portfolio_cash_flow_portfolio",
        "portfolio_cash_flow_history",
        ["portfolio_id"],
    )
    op.create_index(
        "ix_cash_flow_port_currency_effective_seq",
        "portfolio_cash_flow_history",
        [
            "portfolio_id",
            "currency",
            "effective_at",
            "sequence_id",
        ],
    )
    op.create_index(
        "ix_portfolio_cash_flow_effective_at",
        "portfolio_cash_flow_history",
        ["effective_at"],
    )
    op.create_index(
        "ix_portfolio_cash_flow_recorded_at",
        "portfolio_cash_flow_history",
        ["recorded_at"],
    )


def downgrade() -> None:
    """Remove the portfolio cash-flow ledger."""

    op.drop_index(
        "ix_portfolio_cash_flow_recorded_at",
        table_name="portfolio_cash_flow_history",
    )
    op.drop_index(
        "ix_portfolio_cash_flow_effective_at",
        table_name="portfolio_cash_flow_history",
    )
    op.drop_index(
        "ix_cash_flow_port_currency_effective_seq",
        table_name="portfolio_cash_flow_history",
    )
    op.drop_index(
        "ix_portfolio_cash_flow_portfolio",
        table_name="portfolio_cash_flow_history",
    )
    op.drop_table("portfolio_cash_flow_history")

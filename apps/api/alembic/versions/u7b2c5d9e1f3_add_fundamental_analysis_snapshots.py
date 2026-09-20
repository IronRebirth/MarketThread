"""Add persisted fundamental analysis snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "u7b2c5d9e1f3"
down_revision: str | None = "t6a1c9e4b7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the normalized fundamental snapshot table."""

    op.create_table(
        "fundamental_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("revenue_growth", sa.Numeric(20, 8), nullable=True),
        sa.Column("earnings_growth", sa.Numeric(20, 8), nullable=True),
        sa.Column("gross_margin", sa.Numeric(20, 8), nullable=True),
        sa.Column("operating_margin", sa.Numeric(20, 8), nullable=True),
        sa.Column("net_margin", sa.Numeric(20, 8), nullable=True),
        sa.Column("roe", sa.Numeric(20, 8), nullable=True),
        sa.Column("roic", sa.Numeric(20, 8), nullable=True),
        sa.Column("debt_to_equity", sa.Numeric(20, 8), nullable=True),
        sa.Column("debt_to_ebitda", sa.Numeric(20, 8), nullable=True),
        sa.Column("operating_cash_flow", sa.Numeric(24, 8), nullable=True),
        sa.Column("free_cash_flow", sa.Numeric(24, 8), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(20, 8), nullable=True),
        sa.Column("ps_ratio", sa.Numeric(20, 8), nullable=True),
        sa.Column("ev_to_ebitda", sa.Numeric(20, 8), nullable=True),
        sa.Column("dividend_yield", sa.Numeric(20, 8), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "period_end",
            "source",
            name="uq_fundamental_snapshots_instrument_period_source",
        ),
    )
    op.create_index(
        "ix_fundamental_snapshots_instrument_id",
        "fundamental_snapshots",
        ["instrument_id"],
    )
    op.create_index(
        "ix_fundamental_snapshots_period_end",
        "fundamental_snapshots",
        ["period_end"],
    )


def downgrade() -> None:
    """Remove persisted fundamental analysis snapshots."""

    op.drop_index(
        "ix_fundamental_snapshots_period_end",
        table_name="fundamental_snapshots",
    )
    op.drop_index(
        "ix_fundamental_snapshots_instrument_id",
        table_name="fundamental_snapshots",
    )
    op.drop_table("fundamental_snapshots")

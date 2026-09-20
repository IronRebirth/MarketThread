"""Create durable watchlist alert state."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "k1a7d9c4e2b6"
down_revision: str | None = "n5h8k3m1d7p9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create persisted watchlist alert lifecycle state."""

    op.create_table(
        "watchlist_alert_states",
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_item_id", sa.Uuid(), nullable=False),
        sa.Column("market_impact_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="new",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_item_id"],
            ["watchlist_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["market_impact_id"],
            ["market_impacts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("alert_id"),
        sa.UniqueConstraint(
            "watchlist_item_id",
            "market_impact_id",
            name="uq_watchlist_alert_states_item_impact",
        ),
    )

    op.create_index(
        "ix_watchlist_alert_states_watchlist_id",
        "watchlist_alert_states",
        ["watchlist_id"],
    )
    op.create_index(
        "ix_watchlist_alert_states_watchlist_item_id",
        "watchlist_alert_states",
        ["watchlist_item_id"],
    )
    op.create_index(
        "ix_watchlist_alert_states_market_impact_id",
        "watchlist_alert_states",
        ["market_impact_id"],
    )
    op.create_index(
        "ix_watchlist_alert_states_event_id",
        "watchlist_alert_states",
        ["event_id"],
    )
    op.create_index(
        "ix_watchlist_alert_states_status",
        "watchlist_alert_states",
        ["status"],
    )


def downgrade() -> None:
    """Drop persisted watchlist alert lifecycle state."""

    op.drop_index(
        "ix_watchlist_alert_states_status",
        table_name="watchlist_alert_states",
    )
    op.drop_index(
        "ix_watchlist_alert_states_event_id",
        table_name="watchlist_alert_states",
    )
    op.drop_index(
        "ix_watchlist_alert_states_market_impact_id",
        table_name="watchlist_alert_states",
    )
    op.drop_index(
        "ix_watchlist_alert_states_watchlist_item_id",
        table_name="watchlist_alert_states",
    )
    op.drop_index(
        "ix_watchlist_alert_states_watchlist_id",
        table_name="watchlist_alert_states",
    )
    op.drop_table("watchlist_alert_states")

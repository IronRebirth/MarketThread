"""Create persisted in-app watchlist notifications."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "r4c8e1a2b7d6"
down_revision: str | None = "p2b6d9f3a1c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable in-app notification records."""

    op.create_table(
        "watchlist_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("alert_rule_id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("rule_name", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "alert_rule_id",
            "alert_id",
            name="uq_watchlist_notifications_user_rule_alert",
        ),
    )

    op.create_index(
        "ix_watchlist_notifications_user_id",
        "watchlist_notifications",
        ["user_id"],
    )
    op.create_index(
        "ix_watchlist_notifications_watchlist_id",
        "watchlist_notifications",
        ["watchlist_id"],
    )
    op.create_index(
        "ix_watchlist_notifications_alert_rule_id",
        "watchlist_notifications",
        ["alert_rule_id"],
    )
    op.create_index(
        "ix_watchlist_notifications_alert_id",
        "watchlist_notifications",
        ["alert_id"],
    )
    op.create_index(
        "ix_watchlist_notifications_created_at",
        "watchlist_notifications",
        ["created_at"],
    )
    op.create_index(
        "ix_watchlist_notifications_read_at",
        "watchlist_notifications",
        ["read_at"],
    )


def downgrade() -> None:
    """Drop persisted in-app notification records."""

    op.drop_index(
        "ix_watchlist_notifications_read_at",
        table_name="watchlist_notifications",
    )
    op.drop_index(
        "ix_watchlist_notifications_created_at",
        table_name="watchlist_notifications",
    )
    op.drop_index(
        "ix_watchlist_notifications_alert_id",
        table_name="watchlist_notifications",
    )
    op.drop_index(
        "ix_watchlist_notifications_alert_rule_id",
        table_name="watchlist_notifications",
    )
    op.drop_index(
        "ix_watchlist_notifications_watchlist_id",
        table_name="watchlist_notifications",
    )
    op.drop_index(
        "ix_watchlist_notifications_user_id",
        table_name="watchlist_notifications",
    )
    op.drop_table("watchlist_notifications")

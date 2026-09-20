"""Add email notification preferences and delivery state."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "t6a1c9e4b7d8"
down_revision: str | None = "r4c8e1a2b7d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add opt-in email preferences and durable email delivery state."""

    op.add_column(
        "users",
        sa.Column(
            "email_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "notification_email_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "notification_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "recipient_email",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["watchlist_notifications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id",
            name="uq_notification_email_deliveries_notification",
        ),
    )

    op.create_index(
        "ix_notification_email_deliveries_notification_id",
        "notification_email_deliveries",
        ["notification_id"],
    )
    op.create_index(
        "ix_notification_email_deliveries_status",
        "notification_email_deliveries",
        ["status"],
    )
    op.create_index(
        "ix_notification_email_deliveries_created_at",
        "notification_email_deliveries",
        ["created_at"],
    )


def downgrade() -> None:
    """Remove email notification delivery state and preference."""

    op.drop_index(
        "ix_notification_email_deliveries_created_at",
        table_name="notification_email_deliveries",
    )
    op.drop_index(
        "ix_notification_email_deliveries_status",
        table_name="notification_email_deliveries",
    )
    op.drop_index(
        "ix_notification_email_deliveries_notification_id",
        table_name="notification_email_deliveries",
    )
    op.drop_table("notification_email_deliveries")
    op.drop_column("users", "email_notifications_enabled")

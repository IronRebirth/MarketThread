"""Create persisted watchlist alert rules."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2b6d9f3a1c5"
down_revision: str | None = "k1a7d9c4e2b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create notification-eligibility rules for user watchlists."""

    op.create_table(
        "watchlist_alert_rules",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "watchlist_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "rule_type",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "conditions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.CheckConstraint(
            "rule_type IN ('event_impact')",
            name="ck_watchlist_alert_rules_rule_type",
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "watchlist_id",
            "name",
            name="uq_watchlist_alert_rules_watchlist_name",
        ),
    )

    op.create_index(
        "ix_watchlist_alert_rules_watchlist_id",
        "watchlist_alert_rules",
        ["watchlist_id"],
    )
    op.create_index(
        "ix_watchlist_alert_rules_enabled",
        "watchlist_alert_rules",
        ["enabled"],
    )
    op.create_index(
        "ix_watchlist_alert_rules_created_at",
        "watchlist_alert_rules",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop persisted watchlist alert rules."""

    op.drop_index(
        "ix_watchlist_alert_rules_created_at",
        table_name="watchlist_alert_rules",
    )
    op.drop_index(
        "ix_watchlist_alert_rules_enabled",
        table_name="watchlist_alert_rules",
    )
    op.drop_index(
        "ix_watchlist_alert_rules_watchlist_id",
        table_name="watchlist_alert_rules",
    )
    op.drop_table("watchlist_alert_rules")

"""create watchlist tables

Revision ID: j0f4a8c3b6d2
Revises: i9e3c7b2d5f1
Create Date: 2026-09-18 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "j0f4a8c3b6d2"
down_revision: str | None = "i9e3c7b2d5f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watchlists",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "name",
            name="uq_watchlists_user_name",
        ),
    )
    op.create_index(
        "ix_watchlists_user_id",
        "watchlists",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_watchlists_created_at",
        "watchlists",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("watchlist_id", sa.UUID(), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "watchlist_id",
            "instrument_id",
            name="uq_watchlist_items_watchlist_instrument",
        ),
    )
    op.create_index(
        "ix_watchlist_items_watchlist_id",
        "watchlist_items",
        ["watchlist_id"],
        unique=False,
    )
    op.create_index(
        "ix_watchlist_items_instrument_id",
        "watchlist_items",
        ["instrument_id"],
        unique=False,
    )
    op.create_index(
        "ix_watchlist_items_added_at",
        "watchlist_items",
        ["added_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_watchlist_items_added_at",
        table_name="watchlist_items",
    )
    op.drop_index(
        "ix_watchlist_items_instrument_id",
        table_name="watchlist_items",
    )
    op.drop_index(
        "ix_watchlist_items_watchlist_id",
        table_name="watchlist_items",
    )
    op.drop_table("watchlist_items")

    op.drop_index(
        "ix_watchlists_created_at",
        table_name="watchlists",
    )
    op.drop_index(
        "ix_watchlists_user_id",
        table_name="watchlists",
    )
    op.drop_table("watchlists")

"""Create event table."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8d3e2f1a7b4"
down_revision: str | None = "a2c4e6f8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the persisted market-event table."""

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "deduplication_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "catalyst",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "market_relevance",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "impact_direction",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "affected_entities",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "affected_sectors",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "source_article_ids",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deduplication_key",
            name="uq_events_deduplication_key",
        ),
    )

    op.create_index(
        "ix_events_deduplication_key",
        "events",
        ["deduplication_key"],
        unique=True,
    )
    op.create_index(
        "ix_events_event_type",
        "events",
        ["event_type"],
    )
    op.create_index(
        "ix_events_catalyst",
        "events",
        ["catalyst"],
    )
    op.create_index(
        "ix_events_market_relevance",
        "events",
        ["market_relevance"],
    )
    op.create_index(
        "ix_events_impact_direction",
        "events",
        ["impact_direction"],
    )
    op.create_index(
        "ix_events_first_seen_at",
        "events",
        ["first_seen_at"],
    )
    op.create_index(
        "ix_events_last_seen_at",
        "events",
        ["last_seen_at"],
    )


def downgrade() -> None:
    """Drop the persisted market-event table."""

    op.drop_index(
        "ix_events_last_seen_at",
        table_name="events",
    )
    op.drop_index(
        "ix_events_first_seen_at",
        table_name="events",
    )
    op.drop_index(
        "ix_events_impact_direction",
        table_name="events",
    )
    op.drop_index(
        "ix_events_market_relevance",
        table_name="events",
    )
    op.drop_index(
        "ix_events_catalyst",
        table_name="events",
    )
    op.drop_index(
        "ix_events_event_type",
        table_name="events",
    )
    op.drop_index(
        "ix_events_deduplication_key",
        table_name="events",
    )
    op.drop_table("events")

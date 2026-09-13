"""Create news tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d903ad3af48b"
down_revision: str | None = "a410dd03a840"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create news source and article tables."""

    op.create_table(
        "news_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_news_sources_domain",
        "news_sources",
        ["domain"],
        unique=True,
    )

    op.create_table(
        "news_articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["news_sources.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_hash",
            name="uq_news_articles_content_hash",
        ),
    )

    op.create_index(
        "ix_news_articles_source_id",
        "news_articles",
        ["source_id"],
    )
    op.create_index(
        "ix_news_articles_published_at",
        "news_articles",
        ["published_at"],
    )


def downgrade() -> None:
    """Drop news article and source tables."""

    op.drop_index(
        "ix_news_articles_published_at",
        table_name="news_articles",
    )
    op.drop_index(
        "ix_news_articles_source_id",
        table_name="news_articles",
    )
    op.drop_table("news_articles")

    op.drop_index(
        "ix_news_sources_domain",
        table_name="news_sources",
    )
    op.drop_table("news_sources")

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewsSource(Base):
    """News publisher metadata."""

    __tablename__ = "news_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )


class NewsArticle(Base):
    """Persisted normalized news article."""

    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint(
            "content_hash",
            name="uq_news_articles_content_hash",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("news_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    author: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="en",
    )

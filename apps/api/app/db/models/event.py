import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    deduplication_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    catalyst: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    market_relevance: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    impact_direction: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    affected_entities: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    affected_sectors: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    source_article_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(
        nullable=False,
    )

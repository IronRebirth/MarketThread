import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationEmailDeliveryStatus(StrEnum):
    """Persisted email delivery lifecycle states."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationEmailDeliveryRecord(Base):
    """Persisted email delivery attempt state for one in-app notification."""

    __tablename__ = "notification_email_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            name="uq_notification_email_deliveries_notification",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watchlist_notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=NotificationEmailDeliveryStatus.PENDING.value,
        server_default=NotificationEmailDeliveryStatus.PENDING.value,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

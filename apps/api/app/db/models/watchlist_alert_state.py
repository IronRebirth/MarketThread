import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WatchlistAlertStateRecord(Base):
    """Persisted user interaction state for a derived watchlist alert."""

    __tablename__ = "watchlist_alert_states"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'seen', 'acknowledged')",
            name="ck_watchlist_alert_states_status",
        ),
        UniqueConstraint(
            "watchlist_item_id",
            "market_impact_id",
            name="uq_watchlist_alert_states_item_impact",
        ),
    )

    alert_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
    )
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    watchlist_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watchlist_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    market_impact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("market_impacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="new",
        server_default="new",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

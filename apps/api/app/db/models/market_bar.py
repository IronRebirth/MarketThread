import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketBar(Base):
    """Normalized OHLCV market-data bar."""

    __tablename__ = "market_bars"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    open: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )
    high: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )
    low: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )
    close: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )
    volume: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 8),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

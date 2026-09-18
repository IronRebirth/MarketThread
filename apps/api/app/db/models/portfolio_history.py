import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PortfolioPositionHistoryRecord(Base):
    """Append-only historical state of a portfolio position."""

    __tablename__ = "portfolio_position_history"

    sequence_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    id: Mapped[uuid.UUID] = mapped_column(
        unique=True,
        nullable=False,
        default=uuid.uuid4,
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )
    average_cost: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PortfolioCashFlowRecord(Base):
    """Immutable external cash-flow event recorded for a portfolio."""

    __tablename__ = "portfolio_cash_flow_history"
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_portfolio_cash_flow_positive_amount",
        ),
        CheckConstraint(
            "event_type IN ('deposit', 'withdrawal')",
            name="ck_portfolio_cash_flow_event_type",
        ),
        Index(
            "ix_cash_flow_port_currency_effective_seq",
            "portfolio_id",
            "currency",
            "effective_at",
            "sequence_id",
        ),
    )

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
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SignalRecord(Base):
    """Immutable historical snapshot of a generated market signal."""

    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint(
            "market_impact_id",
            name="uq_signals_market_impact",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    market_impact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("market_impacts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
        index=True,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    ticker: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    strength: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    opportunity: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(
        nullable=False,
    )
    risk_score: Mapped[float] = mapped_column(
        nullable=False,
    )
    time_horizon: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    supporting_factors: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    contradicting_factors: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence_article_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    invalidation_conditions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    rationale: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

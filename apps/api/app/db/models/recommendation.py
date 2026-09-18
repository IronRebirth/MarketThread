import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecommendationRecord(Base):
    """Immutable historical snapshot of a generated recommendation."""

    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint(
            "signal_id",
            name="uq_recommendations_signal",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
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
    state: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    signal_direction: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(
        nullable=False,
    )
    risk_score: Mapped[float] = mapped_column(
        nullable=False,
    )
    confidence_level: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    risk_level: Mapped[str] = mapped_column(
        String(32),
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
    assumptions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    invalidation_conditions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence_article_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    rationale: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

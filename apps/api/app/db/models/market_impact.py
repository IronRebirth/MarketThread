import uuid

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketImpactRecord(Base):
    """Persisted market-impact assessment."""

    __tablename__ = "market_impacts"
    __table_args__ = (
        UniqueConstraint(
            "company_impact_id",
            name="uq_market_impacts_company_impact",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    company_impact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("company_impacts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    impact_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    factor: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    time_horizon: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(
        nullable=False,
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

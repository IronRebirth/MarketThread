import uuid

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanyImpactRecord(Base):
    """Persisted company-level impact assessment."""

    __tablename__ = "company_impacts"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "company_name",
            "impact_type",
            name="uq_company_impacts_event_company_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
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
    ticker: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
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
    mechanism: Mapped[str] = mapped_column(
        String,
        nullable=False,
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

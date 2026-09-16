import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BacktestProvenance(Base):
    """Persisted immutable provenance record for a backtest execution."""

    __tablename__ = "backtest_provenance"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
    )
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    stage: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    ruleset_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    input_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence: Mapped[list[dict]] = mapped_column(
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

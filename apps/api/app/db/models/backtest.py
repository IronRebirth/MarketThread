import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BacktestRun(Base):
    """Persisted completed backtest execution."""

    __tablename__ = "backtest_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
    )
    valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    evaluation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    valid_evaluation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    rejected_evaluation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    notes: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class BacktestFold(Base):
    """Persisted walk-forward fold belonging to a backtest run."""

    __tablename__ = "backtest_folds"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
    )
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fold_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    training_periods: Mapped[list[dict[str, str]]] = mapped_column(
        JSON,
        nullable=False,
    )
    evaluation_periods: Mapped[list[dict[str, str]]] = mapped_column(
        JSON,
        nullable=False,
    )
    valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )


class BacktestEvaluation(Base):
    """Persisted time-aware evaluation produced by a backtest fold."""

    __tablename__ = "backtest_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
    )
    fold_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backtest_folds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
        index=True,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
        index=True,
    )
    signal_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    temporal_error: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    signal_direction: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    observed_direction: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    signal_strength: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    recommendation_state: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    signal_confidence: Mapped[float] = mapped_column(
        nullable=False,
    )
    horizon: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        index=True,
    )
    forward_return_pct: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    benchmark_return_pct: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    relative_return_pct: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    direction_correct: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    notes: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

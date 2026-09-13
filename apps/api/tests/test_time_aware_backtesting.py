from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.backtesting.models import (
    BacktestStatus,
    TemporalValidationError,
    TimeAwareObservation,
)
from app.backtesting.service import TimeAwareBacktestService


def make_timestamps() -> tuple[datetime, datetime]:
    """Create a signal timestamp and a later observation timestamp."""

    signal_created_at = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
    observed_at = signal_created_at + timedelta(days=5)

    return signal_created_at, observed_at


def make_observation(observed_at: datetime) -> TimeAwareObservation:
    """Create an observation for temporal validation tests."""

    return TimeAwareObservation(
        instrument_id=uuid4(),
        observed_at=observed_at,
        forward_return_pct=5.0,
        benchmark_return_pct=1.0,
    )


def test_accepts_observation_strictly_after_signal() -> None:
    signal_created_at, observed_at = make_timestamps()

    evaluation = TimeAwareBacktestService().evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        signal_created_at=signal_created_at,
        observation=make_observation(observed_at),
    )

    assert evaluation.status == BacktestStatus.VALID
    assert evaluation.temporal_error is None
    assert evaluation.relative_return_pct == 4.0


def test_rejects_observation_before_signal() -> None:
    signal_created_at, _ = make_timestamps()
    observed_at = signal_created_at - timedelta(days=1)

    evaluation = TimeAwareBacktestService().evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        signal_created_at=signal_created_at,
        observation=make_observation(observed_at),
    )

    assert evaluation.status == BacktestStatus.REJECTED
    assert (
        evaluation.temporal_error == TemporalValidationError.OBSERVATION_BEFORE_SIGNAL
    )
    assert evaluation.relative_return_pct is None


def test_rejects_observation_at_signal_timestamp() -> None:
    signal_created_at, _ = make_timestamps()

    evaluation = TimeAwareBacktestService().evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        signal_created_at=signal_created_at,
        observation=make_observation(signal_created_at),
    )

    assert evaluation.status == BacktestStatus.REJECTED
    assert evaluation.temporal_error == TemporalValidationError.OBSERVATION_AT_SIGNAL


def test_summary_counts_valid_and_rejected_evaluations() -> None:
    signal_created_at, observed_at = make_timestamps()

    service = TimeAwareBacktestService()

    valid = service.evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        signal_created_at=signal_created_at,
        observation=make_observation(observed_at),
    )

    rejected = service.evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        signal_created_at=signal_created_at,
        observation=make_observation(
            signal_created_at - timedelta(days=1),
        ),
    )

    summary = service.summarize((valid, rejected))

    assert summary.total_evaluations == 2
    assert summary.valid_evaluations == 1
    assert summary.rejected_evaluations == 1
    assert summary.average_relative_return_pct == 4.0


def test_empty_summary_is_explicit() -> None:
    summary = TimeAwareBacktestService().summarize(())

    assert summary.total_evaluations == 0
    assert summary.valid_evaluations == 0
    assert summary.rejected_evaluations == 0
    assert summary.average_relative_return_pct is None
    assert "no historical evaluations" in summary.notes[0].lower()


def test_valid_evaluation_documents_temporal_protection() -> None:
    signal_created_at, observed_at = make_timestamps()

    evaluation = TimeAwareBacktestService().evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        signal_created_at=signal_created_at,
        observation=make_observation(observed_at),
    )

    assert any("look-ahead" in note.lower() for note in evaluation.notes)

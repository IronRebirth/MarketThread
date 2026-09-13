from datetime import UTC, datetime
from uuid import uuid4

from app.historical.models import (
    HistoricalOutcome,
    OutcomeDirection,
    OutcomeWindow,
)
from app.historical.service import HistoricalEventAnalysisService


def make_outcome(
    direction: OutcomeDirection,
    return_pct: float | None,
    window: OutcomeWindow = OutcomeWindow.FIVE_DAYS,
) -> HistoricalOutcome:
    """Create an observed historical outcome."""

    timestamp = datetime.now(UTC)

    return HistoricalOutcome(
        event_id=uuid4(),
        instrument_id=uuid4(),
        observed_at=timestamp,
        window=window,
        start_price=100.0 if return_pct is not None else None,
        end_price=105.0 if return_pct is not None else None,
        return_pct=return_pct,
        direction=direction,
        benchmark_return_pct=1.0 if return_pct is not None else None,
        relative_return_pct=(return_pct - 1.0 if return_pct is not None else None),
        source="historical_test",
    )


def test_analyzes_positive_historical_observations() -> None:
    event_id = uuid4()
    analyzed_at = datetime.now(UTC)

    outcomes = (
        make_outcome(OutcomeDirection.POSITIVE, 5.0),
        make_outcome(OutcomeDirection.POSITIVE, 3.0),
        make_outcome(OutcomeDirection.NEGATIVE, -1.0),
    )

    analysis = HistoricalEventAnalysisService().analyze(
        event_id=event_id,
        outcomes=outcomes,
        analyzed_at=analyzed_at,
    )

    assert analysis.event_id == event_id
    assert analysis.observation_count == 3
    assert analysis.outcomes == outcomes
    assert "more observed windows were positive" in " ".join(analysis.notes).lower()


def test_analyzes_negative_majority() -> None:
    event_id = uuid4()
    analyzed_at = datetime.now(UTC)

    outcomes = (
        make_outcome(OutcomeDirection.NEGATIVE, -4.0),
        make_outcome(OutcomeDirection.NEGATIVE, -2.0),
        make_outcome(OutcomeDirection.POSITIVE, 1.0),
    )

    analysis = HistoricalEventAnalysisService().analyze(
        event_id=event_id,
        outcomes=outcomes,
        analyzed_at=analyzed_at,
    )

    assert "more observed windows were negative" in " ".join(analysis.notes).lower()


def test_handles_empty_observations() -> None:
    analysis = HistoricalEventAnalysisService().analyze(
        event_id=uuid4(),
        outcomes=(),
        analyzed_at=datetime.now(UTC),
    )

    assert analysis.observation_count == 0
    assert analysis.outcomes == ()
    assert "no historical market observations" in analysis.notes[0].lower()


def test_handles_unavailable_returns() -> None:
    outcomes = (
        make_outcome(OutcomeDirection.UNAVAILABLE, None),
        make_outcome(OutcomeDirection.UNAVAILABLE, None),
    )

    analysis = HistoricalEventAnalysisService().analyze(
        event_id=uuid4(),
        outcomes=outcomes,
        analyzed_at=datetime.now(UTC),
    )

    assert analysis.observation_count == 2
    assert "return data is unavailable" in " ".join(analysis.notes).lower()


def test_records_relative_return_against_benchmark() -> None:
    outcome = make_outcome(
        OutcomeDirection.POSITIVE,
        5.0,
    )

    assert outcome.benchmark_return_pct == 1.0
    assert outcome.relative_return_pct == 4.0

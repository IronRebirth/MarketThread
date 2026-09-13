from datetime import UTC, datetime
from uuid import uuid4

from app.backtesting.horizon import BacktestHorizon
from app.backtesting.horizon_analyzer import (
    HorizonBacktestAnalyzer,
    HorizonObservation,
)
from app.backtesting.horizon_service import HorizonBacktestService
from app.evaluation.models import EvaluationDirection

UTC = UTC


def make_observation(
    *,
    instrument_id,
    horizon: BacktestHorizon,
    observed_at: datetime,
    forward_return_pct: float | None = 5.0,
    benchmark_return_pct: float | None = 1.0,
) -> HorizonObservation:
    return HorizonObservation(
        instrument_id=instrument_id,
        horizon=horizon,
        observed_at=observed_at,
        forward_return_pct=forward_return_pct,
        benchmark_return_pct=benchmark_return_pct,
    )


def test_horizon_definitions_are_explicit() -> None:
    assert BacktestHorizon.ONE_DAY.value == "1d"
    assert BacktestHorizon.FIVE_DAYS.value == "5d"
    assert BacktestHorizon.TWENTY_DAYS.value == "20d"

    assert BacktestHorizon.ONE_DAY.days == 1
    assert BacktestHorizon.FIVE_DAYS.days == 5
    assert BacktestHorizon.TWENTY_DAYS.days == 20


def test_accepts_matching_horizon_observation() -> None:
    instrument_id = uuid4()
    signal_created_at = datetime(2026, 1, 1, 10, tzinfo=UTC)

    evaluation = HorizonBacktestAnalyzer().evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        signal_created_at=signal_created_at,
        horizon=BacktestHorizon.ONE_DAY,
        observation=make_observation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.ONE_DAY,
            observed_at=datetime(2026, 1, 2, 10, tzinfo=UTC),
        ),
    )

    assert evaluation.valid is True
    assert evaluation.horizon == BacktestHorizon.ONE_DAY
    assert evaluation.forward_return_pct == 5.0
    assert evaluation.relative_return_pct == 4.0


def test_rejects_mismatched_horizon() -> None:
    instrument_id = uuid4()

    evaluation = HorizonBacktestAnalyzer().evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        signal_created_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        horizon=BacktestHorizon.FIVE_DAYS,
        observation=make_observation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.ONE_DAY,
            observed_at=datetime(2026, 1, 2, 10, tzinfo=UTC),
        ),
    )

    assert evaluation.valid is False
    assert "horizon" in evaluation.notes[0].lower()


def test_rejects_observation_at_signal_timestamp() -> None:
    instrument_id = uuid4()
    signal_created_at = datetime(2026, 1, 1, 10, tzinfo=UTC)

    evaluation = HorizonBacktestAnalyzer().evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        signal_created_at=signal_created_at,
        horizon=BacktestHorizon.ONE_DAY,
        observation=make_observation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.ONE_DAY,
            observed_at=signal_created_at,
        ),
    )

    assert evaluation.valid is False
    assert "strictly after" in evaluation.notes[0]


def test_calculates_direction_correctness() -> None:
    instrument_id = uuid4()

    evaluation = HorizonBacktestAnalyzer().evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        signal_created_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        horizon=BacktestHorizon.FIVE_DAYS,
        signal_direction=EvaluationDirection.POSITIVE,
        observation=make_observation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.FIVE_DAYS,
            observed_at=datetime(2026, 1, 6, 10, tzinfo=UTC),
            forward_return_pct=3.0,
        ),
    )

    assert evaluation.observed_direction == EvaluationDirection.POSITIVE
    assert evaluation.direction_correct is True


def test_summarizes_each_supported_horizon() -> None:
    instrument_id = uuid4()

    evaluations = (
        HorizonBacktestService().evaluate(
            signal_id=uuid4(),
            event_id=uuid4(),
            instrument_id=instrument_id,
            signal_created_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
            horizon=BacktestHorizon.ONE_DAY,
            observation=make_observation(
                instrument_id=instrument_id,
                horizon=BacktestHorizon.ONE_DAY,
                observed_at=datetime(2026, 1, 2, 10, tzinfo=UTC),
                forward_return_pct=2.0,
            ),
        ),
        HorizonBacktestService().evaluate(
            signal_id=uuid4(),
            event_id=uuid4(),
            instrument_id=instrument_id,
            signal_created_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
            horizon=BacktestHorizon.FIVE_DAYS,
            observation=make_observation(
                instrument_id=instrument_id,
                horizon=BacktestHorizon.FIVE_DAYS,
                observed_at=datetime(2026, 1, 6, 10, tzinfo=UTC),
                forward_return_pct=5.0,
            ),
        ),
    )

    summaries = HorizonBacktestService().summarize(evaluations)

    assert set(summaries) == {
        BacktestHorizon.ONE_DAY,
        BacktestHorizon.FIVE_DAYS,
        BacktestHorizon.TWENTY_DAYS,
    }

    assert summaries[BacktestHorizon.ONE_DAY]["evaluation_count"] == 1
    assert summaries[BacktestHorizon.FIVE_DAYS]["evaluation_count"] == 1
    assert summaries[BacktestHorizon.TWENTY_DAYS]["evaluation_count"] == 0


def test_missing_observation_is_explicit() -> None:
    evaluation = HorizonBacktestAnalyzer().evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=uuid4(),
        signal_created_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
        horizon=BacktestHorizon.TWENTY_DAYS,
        observation=None,
    )

    assert evaluation.valid is False
    assert "no observation" in evaluation.notes[0].lower()

from datetime import UTC, datetime
from uuid import uuid4

from app.evaluation.models import (
    EvaluationDirection,
    EvaluationWindow,
)
from app.evaluation.service import SignalEvaluationService


def test_evaluates_correct_positive_signal() -> None:
    service = SignalEvaluationService()
    evaluated_at = datetime.now(UTC)

    evaluation = service.evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=uuid4(),
        window=EvaluationWindow.FIVE_DAYS,
        signal_direction=EvaluationDirection.POSITIVE,
        observed_direction=EvaluationDirection.POSITIVE,
        signal_confidence=0.84,
        forward_return_pct=5.0,
        benchmark_return_pct=1.0,
        evaluated_at=evaluated_at,
    )

    assert evaluation.direction_correct is True
    assert evaluation.forward_return_pct == 5.0
    assert evaluation.relative_return_pct == 4.0
    assert evaluation.evaluated_at == evaluated_at


def test_evaluates_incorrect_direction() -> None:
    service = SignalEvaluationService()
    evaluated_at = datetime.now(UTC)

    evaluation = service.evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=uuid4(),
        window=EvaluationWindow.ONE_DAY,
        signal_direction=EvaluationDirection.POSITIVE,
        observed_direction=EvaluationDirection.NEGATIVE,
        signal_confidence=0.72,
        forward_return_pct=-2.0,
        benchmark_return_pct=0.5,
        evaluated_at=evaluated_at,
    )

    assert evaluation.direction_correct is False
    assert evaluation.relative_return_pct == -2.5


def test_neutral_observation_is_not_counted_as_directional_hit() -> None:
    service = SignalEvaluationService()
    evaluated_at = datetime.now(UTC)

    evaluation = service.evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=uuid4(),
        window=EvaluationWindow.TWENTY_DAYS,
        signal_direction=EvaluationDirection.POSITIVE,
        observed_direction=EvaluationDirection.NEUTRAL,
        signal_confidence=0.8,
        forward_return_pct=0.1,
        benchmark_return_pct=0.1,
        evaluated_at=evaluated_at,
    )

    assert evaluation.direction_correct is None


def test_summarizes_evaluation_metrics() -> None:
    service = SignalEvaluationService()
    evaluated_at = datetime.now(UTC)

    evaluations = (
        service.evaluate(
            signal_id=uuid4(),
            event_id=uuid4(),
            instrument_id=uuid4(),
            window=EvaluationWindow.FIVE_DAYS,
            signal_direction=EvaluationDirection.POSITIVE,
            observed_direction=EvaluationDirection.POSITIVE,
            signal_confidence=0.84,
            forward_return_pct=5.0,
            benchmark_return_pct=1.0,
            evaluated_at=evaluated_at,
        ),
        service.evaluate(
            signal_id=uuid4(),
            event_id=uuid4(),
            instrument_id=uuid4(),
            window=EvaluationWindow.FIVE_DAYS,
            signal_direction=EvaluationDirection.POSITIVE,
            observed_direction=EvaluationDirection.NEGATIVE,
            signal_confidence=0.7,
            forward_return_pct=-2.0,
            benchmark_return_pct=1.0,
            evaluated_at=evaluated_at,
        ),
    )

    summary = service.summarize(evaluations)

    assert summary.evaluation_count == 2
    assert summary.directional_accuracy == 0.5
    assert summary.average_forward_return_pct == 1.5
    assert summary.average_relative_return_pct == 0.5
    assert summary.positive_outcome_rate == 0.5


def test_empty_evaluation_summary_is_explicit() -> None:
    summary = SignalEvaluationService().summarize(())

    assert summary.evaluation_count == 0
    assert summary.directional_accuracy is None
    assert summary.average_forward_return_pct is None
    assert summary.average_relative_return_pct is None
    assert summary.positive_outcome_rate is None
    assert "no historical signal evaluations" in summary.notes[0].lower()

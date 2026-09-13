from datetime import UTC, datetime
from uuid import uuid4

from app.evaluation.models import (
    EvaluationByHorizonSummary,
    EvaluationByStateSummary,
    EvaluationDirection,
    EvaluationRecommendationState,
    EvaluationSignalStrength,
    EvaluationWindow,
)
from app.evaluation.service import SignalEvaluationService


def evaluate(
    service: SignalEvaluationService,
    *,
    window: EvaluationWindow,
    signal_direction: EvaluationDirection,
    observed_direction: EvaluationDirection,
    signal_strength: EvaluationSignalStrength = (EvaluationSignalStrength.STRONG),
    recommendation_state: EvaluationRecommendationState = (
        EvaluationRecommendationState.CONSIDER
    ),
    signal_confidence: float = 0.84,
    forward_return_pct: float | None = 5.0,
    benchmark_return_pct: float | None = 1.0,
):
    """Create a signal evaluation for tests."""

    return service.evaluate(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=uuid4(),
        window=window,
        signal_direction=signal_direction,
        observed_direction=observed_direction,
        signal_strength=signal_strength,
        recommendation_state=recommendation_state,
        signal_confidence=signal_confidence,
        forward_return_pct=forward_return_pct,
        benchmark_return_pct=benchmark_return_pct,
        evaluated_at=datetime.now(UTC),
    )


def test_evaluates_signal_with_state_metadata() -> None:
    service = SignalEvaluationService()

    evaluation = evaluate(
        service,
        window=EvaluationWindow.FIVE_DAYS,
        signal_direction=EvaluationDirection.POSITIVE,
        observed_direction=EvaluationDirection.POSITIVE,
        signal_strength=EvaluationSignalStrength.STRONG,
        recommendation_state=EvaluationRecommendationState.CONSIDER,
    )

    assert evaluation.signal_strength == EvaluationSignalStrength.STRONG
    assert evaluation.recommendation_state == EvaluationRecommendationState.CONSIDER
    assert evaluation.direction_correct is True
    assert evaluation.relative_return_pct == 4.0


def test_summarizes_by_signal_strength() -> None:
    service = SignalEvaluationService()

    evaluations = (
        evaluate(
            service,
            window=EvaluationWindow.FIVE_DAYS,
            signal_direction=EvaluationDirection.POSITIVE,
            observed_direction=EvaluationDirection.POSITIVE,
            signal_strength=EvaluationSignalStrength.STRONG,
        ),
        evaluate(
            service,
            window=EvaluationWindow.FIVE_DAYS,
            signal_direction=EvaluationDirection.POSITIVE,
            observed_direction=EvaluationDirection.NEGATIVE,
            signal_strength=EvaluationSignalStrength.STRONG,
            forward_return_pct=-2.0,
            benchmark_return_pct=1.0,
        ),
        evaluate(
            service,
            window=EvaluationWindow.FIVE_DAYS,
            signal_direction=EvaluationDirection.POSITIVE,
            observed_direction=EvaluationDirection.POSITIVE,
            signal_strength=EvaluationSignalStrength.MODERATE,
        ),
    )

    summary = service.summarize_by_signal_strength(evaluations)

    assert isinstance(summary, EvaluationByStateSummary)
    assert len(summary.summaries) == 4

    strong = next(
        item
        for item in summary.summaries
        if item.state == EvaluationSignalStrength.STRONG
    )
    moderate = next(
        item
        for item in summary.summaries
        if item.state == EvaluationSignalStrength.MODERATE
    )

    assert strong.evaluation_count == 2
    assert strong.directional_accuracy == 0.5
    assert strong.average_forward_return_pct == 1.5
    assert strong.average_relative_return_pct == 0.5

    assert moderate.evaluation_count == 1
    assert moderate.directional_accuracy == 1.0
    assert moderate.average_relative_return_pct == 4.0


def test_summarizes_by_recommendation_state() -> None:
    service = SignalEvaluationService()

    evaluations = (
        evaluate(
            service,
            window=EvaluationWindow.ONE_DAY,
            signal_direction=EvaluationDirection.POSITIVE,
            observed_direction=EvaluationDirection.POSITIVE,
            recommendation_state=EvaluationRecommendationState.CONSIDER,
        ),
        evaluate(
            service,
            window=EvaluationWindow.ONE_DAY,
            signal_direction=EvaluationDirection.POSITIVE,
            observed_direction=EvaluationDirection.NEGATIVE,
            recommendation_state=EvaluationRecommendationState.WATCH,
            forward_return_pct=-1.0,
            benchmark_return_pct=0.5,
        ),
        evaluate(
            service,
            window=EvaluationWindow.ONE_DAY,
            signal_direction=EvaluationDirection.NEGATIVE,
            observed_direction=EvaluationDirection.NEGATIVE,
            recommendation_state=EvaluationRecommendationState.REDUCE,
            forward_return_pct=-3.0,
            benchmark_return_pct=1.0,
        ),
    )

    summary = service.summarize_by_recommendation_state(evaluations)

    assert isinstance(summary, EvaluationByStateSummary)
    assert len(summary.summaries) == 5

    consider = next(
        item
        for item in summary.summaries
        if item.state == EvaluationRecommendationState.CONSIDER
    )
    watch = next(
        item
        for item in summary.summaries
        if item.state == EvaluationRecommendationState.WATCH
    )
    reduce = next(
        item
        for item in summary.summaries
        if item.state == EvaluationRecommendationState.REDUCE
    )

    assert consider.evaluation_count == 1
    assert consider.directional_accuracy == 1.0

    assert watch.evaluation_count == 1
    assert watch.directional_accuracy == 0.0
    assert watch.average_relative_return_pct == -1.5

    assert reduce.evaluation_count == 1
    assert reduce.directional_accuracy == 1.0
    assert reduce.average_relative_return_pct == -4.0


def test_state_summaries_include_empty_states() -> None:
    service = SignalEvaluationService()

    summary = service.summarize_by_signal_strength(())

    assert isinstance(summary, EvaluationByStateSummary)
    assert len(summary.summaries) == 4

    for state in summary.summaries:
        assert state.evaluation_count == 0
        assert state.directional_accuracy is None
        assert state.average_forward_return_pct is None
        assert state.average_relative_return_pct is None
        assert state.positive_outcome_rate is None

    assert "no historical signal evaluations" in summary.notes[0].lower()


def test_existing_horizon_summary_remains_available() -> None:
    service = SignalEvaluationService()

    evaluations = (
        evaluate(
            service,
            window=EvaluationWindow.ONE_DAY,
            signal_direction=EvaluationDirection.POSITIVE,
            observed_direction=EvaluationDirection.POSITIVE,
        ),
        evaluate(
            service,
            window=EvaluationWindow.FIVE_DAYS,
            signal_direction=EvaluationDirection.POSITIVE,
            observed_direction=EvaluationDirection.NEGATIVE,
        ),
    )

    summary = service.summarize_by_horizon(evaluations)

    assert isinstance(summary, EvaluationByHorizonSummary)
    assert len(summary.summaries) == 3

    one_day = summary.summaries[0]
    five_day = summary.summaries[1]

    assert one_day.evaluation_count == 1
    assert one_day.directional_accuracy == 1.0

    assert five_day.evaluation_count == 1
    assert five_day.directional_accuracy == 0.0

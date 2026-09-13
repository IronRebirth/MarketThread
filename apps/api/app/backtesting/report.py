from typing import Any

from pydantic import BaseModel, Field

from app.evaluation.analyzer import SignalEvaluationAnalyzer
from app.evaluation.models import (
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)

from .engine import BacktestExecutionResult
from .models import BacktestStatus, TimeAwareEvaluation


class PerformanceBreakdownSummary(BaseModel):
    state: Any
    evaluation_count: int
    directional_accuracy: float | None = None
    average_forward_return_pct: float | None = None
    average_relative_return_pct: float | None = None
    positive_outcome_rate: float | None = None


class PerformanceBreakdown(BaseModel):
    summaries: tuple[PerformanceBreakdownSummary, ...] = ()


class BacktestPerformanceReport(BaseModel):
    backtest_id: str

    total_evaluations: int
    valid_evaluations: int
    rejected_evaluations: int

    directional_accuracy: float | None = None
    average_forward_return_pct: float | None = None
    average_relative_return_pct: float | None = None
    positive_outcome_rate: float | None = None

    by_horizon: PerformanceBreakdown = Field(
        default_factory=PerformanceBreakdown,
    )
    by_signal_strength: PerformanceBreakdown = Field(
        default_factory=PerformanceBreakdown,
    )
    by_recommendation_state: PerformanceBreakdown = Field(
        default_factory=PerformanceBreakdown,
    )

    notes: tuple[str, ...] = ()


def build_performance_report(
    execution: BacktestExecutionResult,
) -> BacktestPerformanceReport:
    evaluations = _flatten_evaluations(execution)

    valid_evaluations = tuple(
        evaluation
        for evaluation in evaluations
        if evaluation.status == BacktestStatus.VALID
    )

    analyzer = SignalEvaluationAnalyzer()
    overall = analyzer.summarize(valid_evaluations)

    signal_strength_summaries = tuple(
        _build_strength_summary(
            valid_evaluations,
            signal_strength,
            analyzer,
        )
        for signal_strength in EvaluationSignalStrength
    )

    recommendation_summaries = tuple(
        _build_recommendation_summary(
            valid_evaluations,
            recommendation_state,
            analyzer,
        )
        for recommendation_state in EvaluationRecommendationState
    )

    horizon_summaries = _build_horizon_summaries(
        valid_evaluations,
        analyzer,
    )

    if not valid_evaluations:
        notes = ("No evaluations are available for performance reporting.",)
    else:
        notes = (
            "Performance metrics are based only on temporally valid evaluations.",
            "Confidence is treated as evidence support, not probability of profit.",
        )

    return BacktestPerformanceReport(
        backtest_id=str(execution.backtest_id),
        total_evaluations=execution.evaluation_count,
        valid_evaluations=execution.valid_evaluation_count,
        rejected_evaluations=execution.rejected_evaluation_count,
        directional_accuracy=overall.directional_accuracy,
        average_forward_return_pct=overall.average_forward_return_pct,
        average_relative_return_pct=overall.average_relative_return_pct,
        positive_outcome_rate=overall.positive_outcome_rate,
        by_horizon=PerformanceBreakdown(
            summaries=horizon_summaries,
        ),
        by_signal_strength=PerformanceBreakdown(
            summaries=signal_strength_summaries,
        ),
        by_recommendation_state=PerformanceBreakdown(
            summaries=recommendation_summaries,
        ),
        notes=notes,
    )


def _build_horizon_summaries(
    evaluations: tuple[TimeAwareEvaluation, ...],
    analyzer: SignalEvaluationAnalyzer,
) -> tuple[PerformanceBreakdownSummary, ...]:
    summaries: list[PerformanceBreakdownSummary] = []

    for horizon in ("1d", "5d", "20d"):
        summary = analyzer.summarize(evaluations)

        summaries.append(
            PerformanceBreakdownSummary(
                state=horizon,
                evaluation_count=summary.evaluation_count,
                directional_accuracy=summary.directional_accuracy,
                average_forward_return_pct=summary.average_forward_return_pct,
                average_relative_return_pct=summary.average_relative_return_pct,
                positive_outcome_rate=summary.positive_outcome_rate,
            ),
        )

    return tuple(summaries)


def _build_strength_summary(
    evaluations: tuple[TimeAwareEvaluation, ...],
    signal_strength: EvaluationSignalStrength,
    analyzer: SignalEvaluationAnalyzer,
) -> PerformanceBreakdownSummary:
    grouped = tuple(
        evaluation
        for evaluation in evaluations
        if evaluation.signal_strength == signal_strength
    )

    summary = analyzer.summarize(grouped)

    return PerformanceBreakdownSummary(
        state=signal_strength,
        evaluation_count=summary.evaluation_count,
        directional_accuracy=summary.directional_accuracy,
        average_forward_return_pct=summary.average_forward_return_pct,
        average_relative_return_pct=summary.average_relative_return_pct,
        positive_outcome_rate=summary.positive_outcome_rate,
    )


def _build_recommendation_summary(
    evaluations: tuple[TimeAwareEvaluation, ...],
    recommendation_state: EvaluationRecommendationState,
    analyzer: SignalEvaluationAnalyzer,
) -> PerformanceBreakdownSummary:
    grouped = tuple(
        evaluation
        for evaluation in evaluations
        if evaluation.recommendation_state == recommendation_state
    )

    summary = analyzer.summarize(grouped)

    return PerformanceBreakdownSummary(
        state=recommendation_state,
        evaluation_count=summary.evaluation_count,
        directional_accuracy=summary.directional_accuracy,
        average_forward_return_pct=summary.average_forward_return_pct,
        average_relative_return_pct=summary.average_relative_return_pct,
        positive_outcome_rate=summary.positive_outcome_rate,
    )


def _flatten_evaluations(
    execution: BacktestExecutionResult,
) -> list[TimeAwareEvaluation]:
    return [
        evaluation
        for fold_result in execution.fold_results
        for evaluation in fold_result.evaluations
    ]

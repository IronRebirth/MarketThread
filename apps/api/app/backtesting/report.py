from typing import Any

from pydantic import BaseModel, Field

from app.evaluation.analyzer import SignalEvaluationAnalyzer
from app.evaluation.models import (
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)

from .engine import BacktestExecutionResult
from .horizon import BacktestHorizon
from .models import BacktestStatus, TimeAwareEvaluation
from .quality import (
    BacktestEvaluationQualityService,
    BacktestQualityAssessment,
)


class PerformanceBreakdownSummary(BaseModel):
    state: Any
    evaluation_count: int
    directional_accuracy: float | None = None
    average_forward_return_pct: float | None = None
    average_relative_return_pct: float | None = None
    positive_outcome_rate: float | None = None
    quality: BacktestQualityAssessment | None = None


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

    quality: BacktestQualityAssessment

    market_data_quality_state: str = "not_assessed"
    market_data_expected_count: int | None = None
    market_data_resolved_count: int | None = None
    market_data_coverage_ratio: float | None = None
    market_data_quality_warnings: tuple[str, ...] = ()

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
    quality_service = BacktestEvaluationQualityService()

    overall = analyzer.summarize(valid_evaluations)

    expected_count = execution.evaluation_count

    quality = quality_service.assess(
        evaluation_count=len(valid_evaluations),
        expected_count=expected_count,
    )

    (
        market_data_quality_state,
        market_data_quality_warnings,
    ) = _assess_market_data_quality(execution)

    horizon_evaluations = tuple(
        evaluation for evaluation in valid_evaluations if evaluation.horizon is not None
    )

    horizon_summaries = _build_horizon_summaries(
        horizon_evaluations,
        quality_service,
        analyzer,
    )

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

    notes = _build_report_notes(
        evaluations=evaluations,
        valid_evaluations=valid_evaluations,
        market_data_quality_state=market_data_quality_state,
        market_data_quality_warnings=market_data_quality_warnings,
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
        quality=quality,
        market_data_quality_state=market_data_quality_state,
        market_data_expected_count=execution.market_data_expected_count,
        market_data_resolved_count=execution.market_data_resolved_count,
        market_data_coverage_ratio=execution.market_data_coverage_ratio,
        market_data_quality_warnings=market_data_quality_warnings,
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


def _assess_market_data_quality(
    execution: BacktestExecutionResult,
) -> tuple[str, tuple[str, ...]]:
    expected = execution.market_data_expected_count
    resolved = execution.market_data_resolved_count
    coverage = execution.market_data_coverage_ratio

    if expected is None or resolved is None:
        return "not_assessed", ()

    if expected == 0:
        return (
            "unavailable",
            ("No deterministic server-side signals were available.",),
        )

    if resolved == 0:
        return (
            "insufficient",
            ("No deterministic signals received usable market-data observations.",),
        )

    if coverage is not None and coverage < 0.95:
        return (
            "insufficient",
            ("Market-data coverage is below the 95% minimum threshold.",),
        )

    return "sufficient", ()


def _build_report_notes(
    *,
    evaluations: tuple[TimeAwareEvaluation, ...] | list[TimeAwareEvaluation],
    valid_evaluations: tuple[TimeAwareEvaluation, ...],
    market_data_quality_state: str,
    market_data_quality_warnings: tuple[str, ...],
) -> tuple[str, ...]:
    if not evaluations:
        notes = [
            "No evaluations are available for performance reporting.",
            "Overall quality is marked as insufficient evidence.",
        ]
    elif not valid_evaluations:
        notes = [
            "No valid evaluations are available for performance reporting.",
            "Overall quality is marked as insufficient evidence.",
        ]
    else:
        notes = [
            "Performance metrics are based only on temporally valid evaluations.",
            "Horizon metrics are derived from horizon-specific backtest evaluations.",
            "Quality state reflects sample size and, when available, "
            "evaluation coverage.",
            "Confidence is treated as evidence support, not probability of profit.",
        ]

    if market_data_quality_state == "sufficient":
        notes.append(
            "Server-side market-data coverage meets the configured 95% threshold.",
        )
    elif market_data_quality_state == "insufficient":
        notes.append(
            "Server-side market-data coverage is insufficient for a complete "
            "historical evaluation.",
        )
        notes.extend(market_data_quality_warnings)
    elif market_data_quality_state == "unavailable":
        notes.append(
            "Server-side market-data coverage could not be established.",
        )

    return tuple(notes)


def _build_horizon_summaries(
    evaluations: tuple[TimeAwareEvaluation, ...],
    quality_service: BacktestEvaluationQualityService,
    analyzer: SignalEvaluationAnalyzer,
) -> tuple[PerformanceBreakdownSummary, ...]:
    summaries: list[PerformanceBreakdownSummary] = []

    for horizon in BacktestHorizon:
        grouped = tuple(
            evaluation for evaluation in evaluations if evaluation.horizon == horizon
        )

        summary = analyzer.summarize(grouped)

        summaries.append(
            PerformanceBreakdownSummary(
                state=horizon,
                evaluation_count=summary.evaluation_count,
                directional_accuracy=summary.directional_accuracy,
                average_forward_return_pct=summary.average_forward_return_pct,
                average_relative_return_pct=summary.average_relative_return_pct,
                positive_outcome_rate=summary.positive_outcome_rate,
                quality=quality_service.assess(
                    evaluation_count=summary.evaluation_count,
                ),
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

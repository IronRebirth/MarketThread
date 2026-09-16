from typing import Any

from pydantic import BaseModel, Field

from app.evaluation.analyzer import SignalEvaluationAnalyzer
from app.evaluation.models import (
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)

from .engine import BacktestExecutionResult
from .horizon import BacktestHorizon
from .market_data_quality import BacktestMarketDataHorizonQuality
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
    market_data_quality: BacktestMarketDataHorizonQuality | None = None


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

    market_data_quality_by_horizon: (
        tuple[BacktestMarketDataHorizonQuality, ...] | None
    ) = None

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

    quality = quality_service.assess(
        evaluation_count=len(valid_evaluations),
        expected_count=execution.evaluation_count,
    )

    horizon_evaluations = tuple(
        evaluation for evaluation in valid_evaluations if evaluation.horizon is not None
    )

    horizon_summaries = _build_horizon_summaries(
        horizon_evaluations,
        quality_service,
        analyzer,
        execution.market_data_horizon_quality,
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

    (
        market_data_quality_state,
        market_data_expected_count,
        market_data_resolved_count,
        market_data_coverage_ratio,
        market_data_quality_warnings,
    ) = _aggregate_market_data_quality(
        execution,
    )

    if not evaluations:
        notes = (
            "No evaluations are available for performance reporting.",
            "Overall quality is marked as insufficient evidence.",
        )
    elif not valid_evaluations:
        notes = (
            "No valid evaluations are available for performance reporting.",
            "Overall quality is marked as insufficient evidence.",
        )
    else:
        notes = (
            "Performance metrics are based only on temporally valid evaluations.",
            "Horizon metrics are derived from horizon-specific backtest evaluations.",
            "Quality state reflects sample size and, when available, "
            "evaluation coverage.",
            "Market-data quality is reported separately from evaluation quality.",
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
        quality=quality,
        market_data_quality_state=market_data_quality_state,
        market_data_expected_count=market_data_expected_count,
        market_data_resolved_count=market_data_resolved_count,
        market_data_coverage_ratio=market_data_coverage_ratio,
        market_data_quality_warnings=market_data_quality_warnings,
        market_data_quality_by_horizon=execution.market_data_horizon_quality,
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


def _aggregate_market_data_quality(
    execution: BacktestExecutionResult,
) -> tuple[
    str,
    int | None,
    int | None,
    float | None,
    tuple[str, ...],
]:
    horizon_quality = execution.market_data_horizon_quality

    if horizon_quality is not None:
        assessed = tuple(item for item in horizon_quality if item.expected_count > 0)

        if not assessed:
            warnings = tuple(
                warning for item in horizon_quality for warning in item.warnings
            )

            return (
                "unavailable",
                0,
                0,
                None,
                warnings,
            )

        expected_count = sum(item.expected_count for item in assessed)

        resolved_count = sum(item.resolved_count for item in assessed)

        coverage_ratio = min(
            resolved_count / expected_count,
            1.0,
        )

        warnings = tuple(warning for item in assessed for warning in item.warnings)

        if all(item.quality_state == "sufficient" for item in assessed):
            state = "sufficient"
        else:
            state = "insufficient"

        return (
            state,
            expected_count,
            resolved_count,
            coverage_ratio,
            warnings,
        )

    expected_count = execution.market_data_expected_count
    resolved_count = execution.market_data_resolved_count

    if expected_count is None or resolved_count is None:
        return (
            "not_assessed",
            None,
            None,
            None,
            (),
        )

    if expected_count == 0:
        return (
            "unavailable",
            0,
            0,
            None,
            (),
        )

    coverage_ratio = min(
        resolved_count / expected_count,
        1.0,
    )

    if resolved_count == 0:
        return (
            "insufficient",
            expected_count,
            resolved_count,
            0.0,
            ("No deterministic signals received usable market-data observations.",),
        )

    if coverage_ratio < 0.95:
        return (
            "insufficient",
            expected_count,
            resolved_count,
            coverage_ratio,
            ("Market-data coverage is below the 95% minimum threshold.",),
        )

    return (
        "sufficient",
        expected_count,
        resolved_count,
        coverage_ratio,
        (),
    )


def _build_horizon_summaries(
    evaluations: tuple[TimeAwareEvaluation, ...],
    quality_service: BacktestEvaluationQualityService,
    analyzer: SignalEvaluationAnalyzer,
    market_data_quality_by_horizon: (
        tuple[BacktestMarketDataHorizonQuality, ...] | None
    ),
) -> tuple[PerformanceBreakdownSummary, ...]:
    summaries: list[PerformanceBreakdownSummary] = []

    market_data_quality_map = {
        item.horizon: item for item in (market_data_quality_by_horizon or ())
    }

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
                market_data_quality=market_data_quality_map.get(horizon),
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

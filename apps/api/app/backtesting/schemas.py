from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .engine import BacktestSignal
from .market_data_quality import BacktestMarketDataHorizonQuality
from .models import BacktestPeriod, TimeAwareObservation
from .report import (
    BacktestPerformanceReport,
    PerformanceBreakdown,
    PerformanceBreakdownSummary,
)


class BacktestPerformanceReportRequest(BaseModel):
    execution: dict = Field(
        description="Serialized BacktestExecutionResult.",
    )


class BacktestRunCreateRequest(BaseModel):
    execution: dict = Field(
        description="Serialized completed BacktestExecutionResult.",
    )


class BacktestExecutionRequest(BaseModel):
    backtest_id: UUID | None = Field(
        default=None,
        description="Optional deterministic identifier for the backtest run.",
    )
    training_periods: tuple[BacktestPeriod, ...] = Field(
        min_length=1,
        description="Chronological training periods.",
    )
    evaluation_periods: tuple[BacktestPeriod, ...] = Field(
        min_length=1,
        description="Chronological evaluation periods.",
    )
    signals: tuple[BacktestSignal, ...] = Field(
        default=(),
    )
    observations: tuple[TimeAwareObservation, ...] = Field(
        default=(),
    )


class ServerSideBacktestExecutionRequest(BaseModel):
    """Configuration for a database-backed historical backtest."""

    backtest_id: UUID | None = Field(
        default=None,
        description="Optional deterministic identifier for the backtest run.",
    )
    training_periods: tuple[BacktestPeriod, ...] = Field(
        min_length=1,
        description="Chronological training periods.",
    )
    evaluation_periods: tuple[BacktestPeriod, ...] = Field(
        min_length=1,
        description="Chronological evaluation periods.",
    )
    benchmark_instrument_id: UUID | None = Field(
        default=None,
        description=(
            "Optional persisted instrument used as the benchmark for "
            "relative-return evaluation."
        ),
    )


class BacktestRunResponse(BaseModel):
    backtest_id: UUID
    valid: bool
    evaluation_count: int
    valid_evaluation_count: int
    rejected_evaluation_count: int
    created_at: datetime
    completed_at: datetime


class BacktestExecutionResponse(BaseModel):
    run: BacktestRunResponse
    report: "BacktestPerformanceReportResponse"


class PerformanceBreakdownSummaryResponse(BaseModel):
    state: str
    evaluation_count: int
    directional_accuracy: float | None = None
    average_forward_return_pct: float | None = None
    average_relative_return_pct: float | None = None
    positive_outcome_rate: float | None = None
    quality_state: str | None = None
    market_data_quality_state: str | None = None


class PerformanceBreakdownResponse(BaseModel):
    summaries: tuple[PerformanceBreakdownSummaryResponse, ...]


class MarketDataHorizonQualityResponse(BaseModel):
    horizon: str
    expected_count: int
    resolved_count: int
    coverage_ratio: float | None
    quality_state: str
    warnings: tuple[str, ...]


class BacktestPerformanceReportResponse(BaseModel):
    backtest_id: str
    total_evaluations: int
    valid_evaluations: int
    rejected_evaluations: int

    directional_accuracy: float | None = None
    average_forward_return_pct: float | None = None
    average_relative_return_pct: float | None = None
    positive_outcome_rate: float | None = None

    quality_state: str
    quality_evaluation_count: int
    quality_expected_count: int | None
    quality_coverage_ratio: float | None
    quality_warnings: tuple[str, ...]

    market_data_quality_state: str
    market_data_expected_count: int | None
    market_data_resolved_count: int | None
    market_data_coverage_ratio: float | None
    market_data_quality_warnings: tuple[str, ...]
    market_data_quality_by_horizon: tuple[MarketDataHorizonQualityResponse, ...] | None

    by_horizon: PerformanceBreakdownResponse
    by_signal_strength: PerformanceBreakdownResponse
    by_recommendation_state: PerformanceBreakdownResponse

    notes: tuple[str, ...]


def to_run_response(
    run: object,
) -> BacktestRunResponse:
    return BacktestRunResponse(
        backtest_id=run.id,
        valid=run.valid,
        evaluation_count=run.evaluation_count,
        valid_evaluation_count=run.valid_evaluation_count,
        rejected_evaluation_count=run.rejected_evaluation_count,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def to_response(
    report: BacktestPerformanceReport,
) -> BacktestPerformanceReportResponse:
    market_data_quality_by_horizon = None

    if report.market_data_quality_by_horizon is not None:
        market_data_quality_by_horizon = tuple(
            _market_data_quality_to_response(item)
            for item in report.market_data_quality_by_horizon
        )

    (
        market_data_quality_state,
        market_data_expected_count,
        market_data_resolved_count,
        market_data_coverage_ratio,
        market_data_quality_warnings,
    ) = _aggregate_market_data_quality(
        report.market_data_quality_by_horizon,
    )

    return BacktestPerformanceReportResponse(
        backtest_id=report.backtest_id,
        total_evaluations=report.total_evaluations,
        valid_evaluations=report.valid_evaluations,
        rejected_evaluations=report.rejected_evaluations,
        directional_accuracy=report.directional_accuracy,
        average_forward_return_pct=report.average_forward_return_pct,
        average_relative_return_pct=report.average_relative_return_pct,
        positive_outcome_rate=report.positive_outcome_rate,
        quality_state=report.quality.state.value,
        quality_evaluation_count=report.quality.evaluation_count,
        quality_expected_count=report.quality.expected_count,
        quality_coverage_ratio=report.quality.coverage_ratio,
        quality_warnings=tuple(warning.value for warning in report.quality.warnings),
        market_data_quality_state=market_data_quality_state,
        market_data_expected_count=market_data_expected_count,
        market_data_resolved_count=market_data_resolved_count,
        market_data_coverage_ratio=market_data_coverage_ratio,
        market_data_quality_warnings=market_data_quality_warnings,
        market_data_quality_by_horizon=market_data_quality_by_horizon,
        by_horizon=_breakdown_to_response(report.by_horizon),
        by_signal_strength=_breakdown_to_response(
            report.by_signal_strength,
        ),
        by_recommendation_state=_breakdown_to_response(
            report.by_recommendation_state,
        ),
        notes=report.notes,
    )


def _aggregate_market_data_quality(
    quality_by_horizon: (tuple[BacktestMarketDataHorizonQuality, ...] | None),
) -> tuple[
    str,
    int | None,
    int | None,
    float | None,
    tuple[str, ...],
]:
    if not quality_by_horizon:
        return (
            "not_assessed",
            None,
            None,
            None,
            (),
        )

    assessed = tuple(item for item in quality_by_horizon if item.expected_count > 0)

    if not assessed:
        warnings = tuple(
            warning for item in quality_by_horizon for warning in item.warnings
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

    states = {item.quality_state for item in assessed}

    if states == {"sufficient"}:
        quality_state = "sufficient"
    else:
        quality_state = "insufficient"

    warnings = tuple(warning for item in assessed for warning in item.warnings)

    return (
        quality_state,
        expected_count,
        resolved_count,
        coverage_ratio,
        warnings,
    )


def _market_data_quality_to_response(
    quality: BacktestMarketDataHorizonQuality,
) -> MarketDataHorizonQualityResponse:
    return MarketDataHorizonQualityResponse(
        horizon=quality.horizon.value,
        expected_count=quality.expected_count,
        resolved_count=quality.resolved_count,
        coverage_ratio=quality.coverage_ratio,
        quality_state=quality.quality_state,
        warnings=quality.warnings,
    )


def _breakdown_to_response(
    breakdown: PerformanceBreakdown,
) -> PerformanceBreakdownResponse:
    return PerformanceBreakdownResponse(
        summaries=tuple(
            _summary_to_response(summary) for summary in breakdown.summaries
        ),
    )


def _summary_to_response(
    summary: PerformanceBreakdownSummary,
) -> PerformanceBreakdownSummaryResponse:
    quality_state = None
    market_data_quality_state = None

    if summary.quality is not None:
        quality_state = summary.quality.state.value

    if summary.market_data_quality is not None:
        market_data_quality_state = summary.market_data_quality.quality_state

    return PerformanceBreakdownSummaryResponse(
        state=(
            str(summary.state.value)
            if hasattr(summary.state, "value")
            else str(summary.state)
        ),
        evaluation_count=summary.evaluation_count,
        directional_accuracy=summary.directional_accuracy,
        average_forward_return_pct=summary.average_forward_return_pct,
        average_relative_return_pct=summary.average_relative_return_pct,
        positive_outcome_rate=summary.positive_outcome_rate,
        quality_state=quality_state,
        market_data_quality_state=market_data_quality_state,
    )

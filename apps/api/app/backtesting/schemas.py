from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .engine import BacktestSignal
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


class PerformanceBreakdownResponse(BaseModel):
    summaries: tuple[PerformanceBreakdownSummaryResponse, ...]


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
        market_data_quality_state=report.market_data_quality_state,
        market_data_expected_count=report.market_data_expected_count,
        market_data_resolved_count=report.market_data_resolved_count,
        market_data_coverage_ratio=report.market_data_coverage_ratio,
        market_data_quality_warnings=report.market_data_quality_warnings,
        by_horizon=_breakdown_to_response(report.by_horizon),
        by_signal_strength=_breakdown_to_response(
            report.by_signal_strength,
        ),
        by_recommendation_state=_breakdown_to_response(
            report.by_recommendation_state,
        ),
        notes=report.notes,
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

    if summary.quality is not None:
        quality_state = summary.quality.state.value

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
    )

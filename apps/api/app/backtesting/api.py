from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from .engine import BacktestExecutionResult
from .report_service import BacktestPerformanceReportService
from .schemas import (
    BacktestPerformanceReportRequest,
    BacktestPerformanceReportResponse,
    to_response,
)

router = APIRouter(
    prefix="/backtests",
    tags=["backtesting"],
)

_report_service = BacktestPerformanceReportService()


@router.post(
    "/performance-report",
    response_model=BacktestPerformanceReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Build a backtest performance report",
    description=(
        "Builds a performance and evidence-quality report from a completed "
        "backtest execution."
    ),
)
def create_performance_report(
    request: BacktestPerformanceReportRequest,
) -> BacktestPerformanceReportResponse:
    try:
        execution = BacktestExecutionResult.model_validate(
            request.execution,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    report = _report_service.build_report(execution)

    return to_response(report)

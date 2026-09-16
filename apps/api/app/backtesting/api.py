from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

from .engine import BacktestExecutionResult
from .orchestration import (
    BacktestExecutionConfigurationError,
    BacktestExecutionOrchestrator,
)
from .persistence import (
    BacktestPersistenceService,
    BacktestRunAlreadyExistsError,
    BacktestRunNotFoundError,
)
from .report_service import BacktestPerformanceReportService
from .resolver import BacktestDataResolutionError, BacktestDataResolver
from .schemas import (
    BacktestExecutionRequest,
    BacktestExecutionResponse,
    BacktestPerformanceReportRequest,
    BacktestPerformanceReportResponse,
    BacktestRunCreateRequest,
    BacktestRunResponse,
    ServerSideBacktestExecutionRequest,
    to_response,
    to_run_response,
)

router = APIRouter(
    prefix="/backtests",
    tags=["backtesting"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

_report_service = BacktestPerformanceReportService()
_persistence_service = BacktestPersistenceService()
_orchestrator = BacktestExecutionOrchestrator(
    persistence_service=_persistence_service,
)
_data_resolver = BacktestDataResolver()


def _validate_execution(
    payload: dict,
) -> BacktestExecutionResult:
    try:
        return BacktestExecutionResult.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc


@router.post(
    "/execute",
    response_model=BacktestExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute and persist a backtest",
    description=(
        "Constructs walk-forward folds, validates their chronology, executes "
        "the supplied signals against historical observations, persists the "
        "completed run, and returns its performance report."
    ),
)
async def execute_backtest(
    request: BacktestExecutionRequest,
    session: DatabaseSession,
) -> BacktestExecutionResponse:
    try:
        execution = await _orchestrator.execute_and_persist(
            session=session,
            training_periods=request.training_periods,
            evaluation_periods=request.evaluation_periods,
            signals=request.signals,
            observations=request.observations,
            backtest_id=request.backtest_id,
        )
    except BacktestExecutionConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except BacktestRunAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    report = _report_service.build_report(execution)

    persisted_run = await _persistence_service.get_run(
        session,
        execution.backtest_id,
    )

    return BacktestExecutionResponse(
        run=to_run_response(persisted_run),
        report=to_response(report),
    )


@router.post(
    "/execute-server-side",
    response_model=BacktestExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a database-backed backtest",
    description=(
        "Resolves persisted market signals and historical market bars on the "
        "server, applies the existing walk-forward temporal controls, "
        "persists the completed run, and returns its performance report."
    ),
)
async def execute_server_side_backtest(
    request: ServerSideBacktestExecutionRequest,
    session: DatabaseSession,
) -> BacktestExecutionResponse:
    try:
        resolution = await _data_resolver.resolve(
            session,
            evaluation_periods=request.evaluation_periods,
            benchmark_instrument_id=request.benchmark_instrument_id,
        )

        execution = await _orchestrator.execute_and_persist(
            session=session,
            training_periods=request.training_periods,
            evaluation_periods=request.evaluation_periods,
            signals=resolution.signals,
            observations=resolution.observations,
            backtest_id=request.backtest_id,
            market_data_expected_count=resolution.market_data_expected_count,
            market_data_resolved_count=resolution.market_data_resolved_count,
            market_data_horizon_quality=resolution.market_data_horizon_quality,
        )

        if resolution.notes:
            run = await _persistence_service.get_run(
                session,
                execution.backtest_id,
            )
            run.notes = list(execution.notes + resolution.notes)
            await session.commit()
            await session.refresh(run)

    except BacktestDataResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except BacktestExecutionConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except BacktestRunAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    report = _report_service.build_report(execution)

    persisted_run = await _persistence_service.get_run(
        session,
        execution.backtest_id,
    )

    return BacktestExecutionResponse(
        run=to_run_response(persisted_run),
        report=to_response(report),
    )


@router.post(
    "/runs",
    response_model=BacktestRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persist a completed backtest run",
    description=(
        "Persists a completed backtest execution including its walk-forward "
        "folds and time-aware evaluations."
    ),
)
async def create_backtest_run(
    request: BacktestRunCreateRequest,
    session: DatabaseSession,
) -> BacktestRunResponse:
    execution = _validate_execution(request.execution)

    try:
        run = await _persistence_service.save_execution(
            session,
            execution,
        )
    except BacktestRunAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return to_run_response(run)


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
    execution = _validate_execution(request.execution)

    report = _report_service.build_report(execution)

    return to_response(report)


@router.get(
    "/runs/latest/performance-report",
    response_model=BacktestPerformanceReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the latest persisted backtest report",
)
async def get_latest_backtest_report(
    session: DatabaseSession,
) -> BacktestPerformanceReportResponse:
    execution = await _persistence_service.get_latest_execution(session)

    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No persisted backtest runs are available.",
        )

    report = _report_service.build_report(execution)

    return to_response(report)


@router.get(
    "/runs/{backtest_id}/performance-report",
    response_model=BacktestPerformanceReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a persisted backtest report",
)
async def get_backtest_report(
    backtest_id: UUID,
    session: DatabaseSession,
) -> BacktestPerformanceReportResponse:
    try:
        execution = await _persistence_service.get_execution(
            session,
            backtest_id,
        )
    except BacktestRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    report = _report_service.build_report(execution)

    return to_response(report)

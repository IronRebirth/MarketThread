from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.backtest import (
    BacktestEvaluation,
    BacktestFold,
    BacktestRun,
)

from .horizon import BacktestHorizon
from .market_data_quality import BacktestMarketDataHorizonQuality
from .models import (
    BacktestExecutionResult,
    BacktestFoldResult,
    BacktestPeriod,
    TimeAwareEvaluation,
)


class BacktestPersistenceError(Exception):
    """Base error for persisted backtest operations."""


class BacktestRunAlreadyExistsError(BacktestPersistenceError):
    """Raised when a backtest ID is already persisted."""


class BacktestRunNotFoundError(BacktestPersistenceError):
    """Raised when a requested backtest run does not exist."""


class BacktestPersistenceService:
    """Persist and restore completed backtest executions."""

    async def save_execution(
        self,
        session: AsyncSession,
        execution: BacktestExecutionResult,
    ) -> BacktestRun:
        existing = await session.get(
            BacktestRun,
            execution.backtest_id,
        )

        if existing is not None:
            raise BacktestRunAlreadyExistsError(
                f"Backtest run {execution.backtest_id} already exists.",
            )

        completed_at = datetime.now(UTC)

        run = BacktestRun(
            id=execution.backtest_id,
            valid=execution.valid,
            evaluation_count=execution.evaluation_count,
            valid_evaluation_count=execution.valid_evaluation_count,
            rejected_evaluation_count=execution.rejected_evaluation_count,
            market_data_expected_count=execution.market_data_expected_count,
            market_data_resolved_count=execution.market_data_resolved_count,
            market_data_coverage_ratio=execution.market_data_coverage_ratio,
            market_data_horizon_quality=(
                [
                    quality.model_dump(mode="json")
                    for quality in execution.market_data_horizon_quality
                ]
                if execution.market_data_horizon_quality is not None
                else None
            ),
            notes=list(execution.notes),
            completed_at=completed_at,
            created_at=completed_at,
        )

        session.add(run)

        await session.flush()

        for fold_result in execution.fold_results:
            fold = self._build_fold(
                backtest_id=execution.backtest_id,
                fold_result=fold_result,
            )

            session.add(fold)

            await session.flush()

            for evaluation in fold_result.evaluations:
                session.add(
                    self._build_evaluation(
                        fold_id=fold.id,
                        evaluation=evaluation,
                    ),
                )

        await session.commit()
        await session.refresh(run)

        return run

    async def get_run(
        self,
        session: AsyncSession,
        backtest_id: UUID,
    ) -> BacktestRun:
        """Retrieve persisted run metadata by ID."""

        run = await session.get(
            BacktestRun,
            backtest_id,
        )

        if run is None:
            raise BacktestRunNotFoundError(
                f"Backtest run {backtest_id} was not found.",
            )

        return run

    async def list_runs(
        self,
        session: AsyncSession,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[tuple[BacktestRun, ...], int]:
        """Retrieve persisted backtest runs in reverse completion order."""

        count_result = await session.execute(
            select(func.count()).select_from(BacktestRun),
        )

        total = int(count_result.scalar_one())

        if total == 0 or offset >= total:
            return (), total

        result = await session.execute(
            select(BacktestRun)
            .order_by(
                BacktestRun.completed_at.desc(),
                BacktestRun.created_at.desc(),
            )
            .offset(offset)
            .limit(limit),
        )

        runs = tuple(result.scalars().all())

        return runs, total

    async def list_evaluations(
        self,
        session: AsyncSession,
        backtest_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[tuple[BacktestEvaluation, int], int]:
        """Retrieve persisted evaluations for a backtest with fold numbers."""

        count_result = await session.execute(
            select(func.count())
            .select_from(BacktestEvaluation)
            .join(
                BacktestFold,
                BacktestEvaluation.fold_id == BacktestFold.id,
            )
            .where(
                BacktestFold.backtest_id == backtest_id,
            ),
        )

        total = int(count_result.scalar_one())

        if total == 0 or offset >= total:
            return (), total

        result = await session.execute(
            select(
                BacktestEvaluation,
                BacktestFold.fold_number,
            )
            .join(
                BacktestFold,
                BacktestEvaluation.fold_id == BacktestFold.id,
            )
            .where(
                BacktestFold.backtest_id == backtest_id,
            )
            .order_by(
                BacktestFold.fold_number,
                BacktestEvaluation.signal_created_at,
                BacktestEvaluation.id,
            )
            .offset(offset)
            .limit(limit),
        )

        rows = tuple(result.all())

        return rows, total

    async def get_execution(
        self,
        session: AsyncSession,
        backtest_id: UUID,
    ) -> BacktestExecutionResult:
        run = await session.get(
            BacktestRun,
            backtest_id,
        )

        if run is None:
            raise BacktestRunNotFoundError(
                f"Backtest run {backtest_id} was not found.",
            )

        return await self._restore_execution(
            session=session,
            run=run,
        )

    async def get_latest_execution(
        self,
        session: AsyncSession,
    ) -> BacktestExecutionResult | None:
        result = await session.execute(
            select(BacktestRun)
            .order_by(
                BacktestRun.completed_at.desc(),
                BacktestRun.created_at.desc(),
            )
            .limit(1),
        )

        run = result.scalar_one_or_none()

        if run is None:
            return None

        return await self._restore_execution(
            session=session,
            run=run,
        )

    async def _restore_execution(
        self,
        *,
        session: AsyncSession,
        run: BacktestRun,
    ) -> BacktestExecutionResult:
        folds_result = await session.execute(
            select(BacktestFold)
            .where(BacktestFold.backtest_id == run.id)
            .order_by(BacktestFold.fold_number),
        )

        fold_rows = tuple(folds_result.scalars().all())

        fold_results: list[BacktestFoldResult] = []

        for fold_row in fold_rows:
            evaluations_result = await session.execute(
                select(BacktestEvaluation)
                .where(
                    BacktestEvaluation.fold_id == fold_row.id,
                )
                .order_by(BacktestEvaluation.signal_created_at),
            )

            evaluation_rows = tuple(evaluations_result.scalars().all())

            fold_results.append(
                BacktestFoldResult(
                    fold_number=fold_row.fold_number,
                    training_periods=tuple(
                        self._period_from_payload(period)
                        for period in fold_row.training_periods
                    ),
                    evaluation_periods=tuple(
                        self._period_from_payload(period)
                        for period in fold_row.evaluation_periods
                    ),
                    evaluations=tuple(
                        self._evaluation_from_row(row) for row in evaluation_rows
                    ),
                    valid=fold_row.valid,
                ),
            )

        horizon_quality = None

        if run.market_data_horizon_quality is not None:
            horizon_quality = tuple(
                BacktestMarketDataHorizonQuality.model_validate(item)
                for item in run.market_data_horizon_quality
            )

        return BacktestExecutionResult(
            backtest_id=run.id,
            fold_results=tuple(fold_results),
            valid=run.valid,
            evaluation_count=run.evaluation_count,
            valid_evaluation_count=run.valid_evaluation_count,
            rejected_evaluation_count=run.rejected_evaluation_count,
            market_data_expected_count=run.market_data_expected_count,
            market_data_resolved_count=run.market_data_resolved_count,
            market_data_coverage_ratio=run.market_data_coverage_ratio,
            market_data_horizon_quality=horizon_quality,
            notes=tuple(run.notes),
        )

    @staticmethod
    def _build_fold(
        *,
        backtest_id: UUID,
        fold_result: BacktestFoldResult,
    ) -> BacktestFold:
        return BacktestFold(
            id=uuid4(),
            backtest_id=backtest_id,
            fold_number=fold_result.fold_number,
            training_periods=[
                {
                    "start_at": period.start_at.isoformat(),
                    "end_at": period.end_at.isoformat(),
                }
                for period in fold_result.training_periods
            ],
            evaluation_periods=[
                {
                    "start_at": period.start_at.isoformat(),
                    "end_at": period.end_at.isoformat(),
                }
                for period in fold_result.evaluation_periods
            ],
            valid=fold_result.valid,
        )

    @staticmethod
    def _build_evaluation(
        *,
        fold_id: UUID,
        evaluation: TimeAwareEvaluation,
    ) -> BacktestEvaluation:
        return BacktestEvaluation(
            id=uuid4(),
            fold_id=fold_id,
            signal_id=evaluation.signal_id,
            event_id=evaluation.event_id,
            instrument_id=evaluation.instrument_id,
            signal_created_at=evaluation.signal_created_at,
            status=evaluation.status.value,
            temporal_error=(
                evaluation.temporal_error.value
                if evaluation.temporal_error is not None
                else None
            ),
            signal_direction=evaluation.signal_direction.value,
            observed_direction=evaluation.observed_direction.value,
            signal_strength=evaluation.signal_strength.value,
            recommendation_state=evaluation.recommendation_state.value,
            signal_confidence=evaluation.signal_confidence,
            horizon=(
                evaluation.horizon.value if evaluation.horizon is not None else None
            ),
            forward_return_pct=evaluation.forward_return_pct,
            benchmark_return_pct=evaluation.benchmark_return_pct,
            relative_return_pct=evaluation.relative_return_pct,
            direction_correct=evaluation.direction_correct,
            notes=list(evaluation.notes),
        )

    @staticmethod
    def _period_from_payload(
        payload: dict[str, str],
    ) -> BacktestPeriod:
        return BacktestPeriod(
            start_at=datetime.fromisoformat(payload["start_at"]),
            end_at=datetime.fromisoformat(payload["end_at"]),
        )

    @staticmethod
    def _evaluation_from_row(
        row: BacktestEvaluation,
    ) -> TimeAwareEvaluation:
        return TimeAwareEvaluation(
            signal_id=row.signal_id,
            event_id=row.event_id,
            instrument_id=row.instrument_id,
            signal_created_at=row.signal_created_at,
            status=row.status,
            temporal_error=row.temporal_error,
            signal_direction=row.signal_direction,
            observed_direction=row.observed_direction,
            signal_strength=row.signal_strength,
            recommendation_state=row.recommendation_state,
            signal_confidence=row.signal_confidence,
            horizon=(BacktestHorizon(row.horizon) if row.horizon is not None else None),
            forward_return_pct=row.forward_return_pct,
            benchmark_return_pct=row.benchmark_return_pct,
            relative_return_pct=row.relative_return_pct,
            direction_correct=row.direction_correct,
            notes=tuple(row.notes),
        )

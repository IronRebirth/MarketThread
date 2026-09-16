from uuid import UUID, uuid4

from app.provenance.models import AnalysisStage
from app.provenance.persistence import ProvenancePersistenceService
from app.provenance.service import ProvenanceService

from .engine import BacktestSignal
from .market_data_quality import BacktestMarketDataHorizonQuality
from .models import (
    BacktestExecutionResult,
    BacktestPeriod,
    TimeAwareObservation,
    WalkForwardResult,
)
from .persistence import BacktestPersistenceService
from .service import BacktestExecutionService
from .walk_forward import WalkForwardBacktestAnalyzer


class BacktestExecutionConfigurationError(ValueError):
    """Raised when a backtest configuration fails temporal validation."""


class BacktestExecutionOrchestrator:
    """Coordinate backtest construction, validation, execution, and persistence."""

    def __init__(
        self,
        *,
        walk_forward_analyzer: WalkForwardBacktestAnalyzer | None = None,
        execution_service: BacktestExecutionService | None = None,
        persistence_service: BacktestPersistenceService | None = None,
        provenance_service: ProvenanceService | None = None,
        provenance_persistence_service: ProvenancePersistenceService | None = None,
    ) -> None:
        self._walk_forward_analyzer = (
            walk_forward_analyzer or WalkForwardBacktestAnalyzer()
        )
        self._execution_service = execution_service or BacktestExecutionService()
        self._persistence_service = persistence_service or BacktestPersistenceService()
        self._provenance_service = provenance_service or ProvenanceService()
        self._provenance_persistence_service = (
            provenance_persistence_service or ProvenancePersistenceService()
        )

    async def execute_and_persist(
        self,
        *,
        session,
        training_periods: tuple[BacktestPeriod, ...],
        evaluation_periods: tuple[BacktestPeriod, ...],
        signals: tuple[BacktestSignal, ...],
        observations: tuple[TimeAwareObservation, ...],
        backtest_id: UUID | None = None,
        market_data_expected_count: int | None = None,
        market_data_resolved_count: int | None = None,
        market_data_horizon_quality: (
            tuple[BacktestMarketDataHorizonQuality, ...] | None
        ) = None,
    ) -> BacktestExecutionResult:
        resolved_backtest_id = backtest_id or uuid4()

        folds = self._walk_forward_analyzer.create_folds(
            training_periods,
            evaluation_periods,
        )

        validation = self._walk_forward_analyzer.validate(
            folds,
            backtest_id=resolved_backtest_id,
        )

        self._ensure_valid_configuration(validation)

        execution = self._execution_service.execute(
            folds=validation.folds,
            signals=signals,
            observations=observations,
            backtest_id=resolved_backtest_id,
            market_data_expected_count=market_data_expected_count,
            market_data_resolved_count=market_data_resolved_count,
            market_data_horizon_quality=market_data_horizon_quality,
        )

        await self._persistence_service.save_execution(
            session,
            execution,
        )

        provenance = self._provenance_service.create_record(
            result_id=execution.backtest_id,
            stage=AnalysisStage.BACKTESTING,
            input_ids=tuple(signal.signal_id for signal in signals),
            evidence=(),
            assumptions=execution.notes,
            invalidation_conditions=(
                "Persisted backtest inputs or historical observations are changed.",
                "The backtest execution ruleset changes.",
            ),
        )

        await self._provenance_persistence_service.save(
            session,
            provenance,
        )

        return execution

    @staticmethod
    def _ensure_valid_configuration(
        validation: WalkForwardResult,
    ) -> None:
        if validation.valid:
            return

        detail = "Backtest configuration failed temporal validation."

        if validation.notes:
            detail = f"{detail} {' '.join(validation.notes)}"

        raise BacktestExecutionConfigurationError(detail)

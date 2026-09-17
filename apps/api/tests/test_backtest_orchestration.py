from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.backtesting.engine import BacktestSignal
from app.backtesting.models import BacktestPeriod, TimeAwareObservation
from app.backtesting.orchestration import (
    BacktestExecutionConfigurationError,
    BacktestExecutionOrchestrator,
)
from app.evaluation.models import (
    EvaluationDirection,
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)
from app.provenance.models import ProvenanceRecord


def _period(
    start: str,
    end: str,
) -> BacktestPeriod:
    return BacktestPeriod(
        start_at=datetime.fromisoformat(start),
        end_at=datetime.fromisoformat(end),
    )


def _signal(
    *,
    instrument_id,
    created_at: str,
) -> BacktestSignal:
    return BacktestSignal(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        created_at=datetime.fromisoformat(created_at),
        direction=EvaluationDirection.POSITIVE,
        signal_strength=EvaluationSignalStrength.STRONG,
        recommendation_state=EvaluationRecommendationState.CONSIDER,
        confidence=0.9,
    )


class FakePersistenceService:
    def __init__(self) -> None:
        self.saved_execution = None
        self.saved_configuration = None

    async def save_execution(
        self,
        session,
        execution,
        *,
        configuration=None,
    ):
        self.saved_execution = execution
        self.saved_configuration = configuration
        return execution


class FakeProvenancePersistenceService:
    def __init__(self) -> None:
        self.saved_record: ProvenanceRecord | None = None

    async def save(
        self,
        session,
        record: ProvenanceRecord,
    ):
        self.saved_record = record
        return record


@pytest.mark.asyncio
async def test_orchestrator_builds_valid_execution_before_persistence():
    instrument_id = uuid4()
    persistence = FakePersistenceService()
    provenance_persistence = FakeProvenancePersistenceService()
    orchestrator = BacktestExecutionOrchestrator(
        persistence_service=persistence,
        provenance_persistence_service=provenance_persistence,
    )

    signal = _signal(
        instrument_id=instrument_id,
        created_at="2021-02-01T00:00:00+00:00",
    )

    training_periods = (
        _period(
            "2020-01-01T00:00:00+00:00",
            "2021-01-01T00:00:00+00:00",
        ),
    )

    evaluation_periods = (
        _period(
            "2021-01-01T00:00:00+00:00",
            "2022-01-01T00:00:00+00:00",
        ),
    )

    observation = TimeAwareObservation(
        instrument_id=instrument_id,
        observed_at=datetime(
            2021,
            2,
            2,
            tzinfo=UTC,
        ),
        forward_return_pct=2.0,
        benchmark_return_pct=1.0,
    )

    execution = await orchestrator.execute_and_persist(
        session=object(),
        training_periods=training_periods,
        evaluation_periods=evaluation_periods,
        signals=(signal,),
        observations=(observation,),
    )

    assert execution.valid is True
    assert execution.evaluation_count == 1
    assert execution.valid_evaluation_count == 1
    assert persistence.saved_execution is execution

    assert persistence.saved_configuration is not None
    assert persistence.saved_configuration.training_periods == training_periods
    assert persistence.saved_configuration.evaluation_periods == evaluation_periods
    assert persistence.saved_configuration.benchmark_instrument_id is None

    assert provenance_persistence.saved_record is not None
    assert provenance_persistence.saved_record.result_id == execution.backtest_id
    assert provenance_persistence.saved_record.input_ids == (signal.signal_id,)


@pytest.mark.asyncio
async def test_orchestrator_persists_benchmark_in_configuration():
    benchmark_instrument_id = uuid4()
    persistence = FakePersistenceService()
    provenance_persistence = FakeProvenancePersistenceService()
    orchestrator = BacktestExecutionOrchestrator(
        persistence_service=persistence,
        provenance_persistence_service=provenance_persistence,
    )

    training_periods = (
        _period(
            "2020-01-01T00:00:00+00:00",
            "2021-01-01T00:00:00+00:00",
        ),
    )

    evaluation_periods = (
        _period(
            "2021-01-01T00:00:00+00:00",
            "2022-01-01T00:00:00+00:00",
        ),
    )

    await orchestrator.execute_and_persist(
        session=object(),
        training_periods=training_periods,
        evaluation_periods=evaluation_periods,
        signals=(),
        observations=(),
        benchmark_instrument_id=benchmark_instrument_id,
    )

    assert persistence.saved_configuration is not None
    assert (
        persistence.saved_configuration.benchmark_instrument_id
        == benchmark_instrument_id
    )


@pytest.mark.asyncio
async def test_orchestrator_rejects_invalid_walk_forward_configuration():
    persistence = FakePersistenceService()
    provenance_persistence = FakeProvenancePersistenceService()
    orchestrator = BacktestExecutionOrchestrator(
        persistence_service=persistence,
        provenance_persistence_service=provenance_persistence,
    )

    with pytest.raises(BacktestExecutionConfigurationError):
        await orchestrator.execute_and_persist(
            session=object(),
            training_periods=(
                _period(
                    "2021-01-01T00:00:00+00:00",
                    "2022-01-01T00:00:00+00:00",
                ),
            ),
            evaluation_periods=(
                _period(
                    "2021-06-01T00:00:00+00:00",
                    "2023-01-01T00:00:00+00:00",
                ),
            ),
            signals=(),
            observations=(),
        )

    assert persistence.saved_execution is None
    assert persistence.saved_configuration is None
    assert provenance_persistence.saved_record is None

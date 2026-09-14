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

    async def save_execution(
        self,
        session,
        execution,
    ):
        self.saved_execution = execution
        return execution


@pytest.mark.asyncio
async def test_orchestrator_builds_valid_execution_before_persistence():
    instrument_id = uuid4()
    persistence = FakePersistenceService()
    orchestrator = BacktestExecutionOrchestrator(
        persistence_service=persistence,
    )

    signal = _signal(
        instrument_id=instrument_id,
        created_at="2021-02-01T00:00:00+00:00",
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
        training_periods=(
            _period(
                "2020-01-01T00:00:00+00:00",
                "2021-01-01T00:00:00+00:00",
            ),
        ),
        evaluation_periods=(
            _period(
                "2021-01-01T00:00:00+00:00",
                "2022-01-01T00:00:00+00:00",
            ),
        ),
        signals=(signal,),
        observations=(observation,),
    )

    assert execution.valid is True
    assert execution.evaluation_count == 1
    assert execution.valid_evaluation_count == 1
    assert persistence.saved_execution is execution


@pytest.mark.asyncio
async def test_orchestrator_rejects_invalid_walk_forward_configuration():
    persistence = FakePersistenceService()
    orchestrator = BacktestExecutionOrchestrator(
        persistence_service=persistence,
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

from datetime import datetime
from uuid import uuid4

import pytest

from app.backtesting.models import (
    BacktestExecutionResult,
    BacktestPeriod,
    BacktestRunConfiguration,
)
from app.backtesting.persistence import BacktestPersistenceService
from app.db.models.backtest import BacktestRun


def _period(
    start: str,
    end: str,
) -> BacktestPeriod:
    return BacktestPeriod(
        start_at=datetime.fromisoformat(start),
        end_at=datetime.fromisoformat(end),
    )


class FakeSession:
    def __init__(self) -> None:
        self.run: BacktestRun | None = None

    async def get(self, model, identifier):
        assert model is BacktestRun
        return None

    def add(self, item) -> None:
        if isinstance(item, BacktestRun):
            self.run = item

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def refresh(self, item) -> None:
        return None


@pytest.mark.asyncio
async def test_save_execution_persists_configuration_snapshot():
    backtest_id = uuid4()

    execution = BacktestExecutionResult(
        backtest_id=backtest_id,
        valid=True,
        evaluation_count=0,
        valid_evaluation_count=0,
        rejected_evaluation_count=0,
    )

    configuration = BacktestRunConfiguration(
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
        benchmark_instrument_id=uuid4(),
    )

    session = FakeSession()

    run = await BacktestPersistenceService().save_execution(
        session,
        execution,
        configuration=configuration,
    )

    assert run is session.run
    assert run.configuration is not None
    assert run.configuration["benchmark_instrument_id"] == str(
        configuration.benchmark_instrument_id,
    )
    assert run.configuration["training_periods"] == [
        {
            "start_at": "2020-01-01T00:00:00Z",
            "end_at": "2021-01-01T00:00:00Z",
        },
    ]
    assert run.configuration["evaluation_periods"] == [
        {
            "start_at": "2021-01-01T00:00:00Z",
            "end_at": "2022-01-01T00:00:00Z",
        },
    ]


@pytest.mark.asyncio
async def test_save_execution_remains_backward_compatible_without_configuration():
    execution = BacktestExecutionResult(
        backtest_id=uuid4(),
        valid=True,
        evaluation_count=0,
        valid_evaluation_count=0,
        rejected_evaluation_count=0,
    )

    session = FakeSession()

    run = await BacktestPersistenceService().save_execution(
        session,
        execution,
    )

    assert run.configuration is None

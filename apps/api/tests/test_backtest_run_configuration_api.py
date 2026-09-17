from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.backtesting.api as backtest_api
from app.db.session import get_db_session

api_app = FastAPI()
api_app.include_router(backtest_api.router)


async def override_get_db_session():
    yield object()


api_app.dependency_overrides[get_db_session] = override_get_db_session

client = TestClient(api_app)


def _execution_payload(backtest_id):
    return {
        "backtest_id": str(backtest_id),
        "fold_results": [],
        "valid": True,
        "evaluation_count": 0,
        "valid_evaluation_count": 0,
        "rejected_evaluation_count": 0,
        "market_data_expected_count": None,
        "market_data_resolved_count": None,
        "market_data_coverage_ratio": None,
        "market_data_horizon_quality": None,
        "notes": [],
    }


def _configuration_payload(benchmark_instrument_id):
    return {
        "training_periods": [
            {
                "start_at": "2020-01-01T00:00:00+00:00",
                "end_at": "2021-01-01T00:00:00+00:00",
            },
        ],
        "evaluation_periods": [
            {
                "start_at": "2021-01-01T00:00:00+00:00",
                "end_at": "2022-01-01T00:00:00+00:00",
            },
        ],
        "benchmark_instrument_id": str(benchmark_instrument_id),
    }


class FakePersistenceService:
    def __init__(self) -> None:
        self.saved_configuration = None

    async def save_execution(
        self,
        session,
        execution,
        *,
        configuration=None,
    ):
        self.saved_configuration = configuration

        timestamp = datetime.now(UTC)

        return SimpleNamespace(
            id=execution.backtest_id,
            valid=execution.valid,
            evaluation_count=execution.evaluation_count,
            valid_evaluation_count=execution.valid_evaluation_count,
            rejected_evaluation_count=execution.rejected_evaluation_count,
            configuration=(
                configuration.model_dump(mode="json")
                if configuration is not None
                else None
            ),
            created_at=timestamp,
            completed_at=timestamp,
        )


def test_create_backtest_run_returns_persisted_configuration(monkeypatch) -> None:
    persistence = FakePersistenceService()

    monkeypatch.setattr(
        backtest_api,
        "_persistence_service",
        persistence,
    )

    backtest_id = uuid4()
    benchmark_instrument_id = uuid4()

    response = client.post(
        "/backtests/runs",
        json={
            "execution": _execution_payload(backtest_id),
            "configuration": _configuration_payload(
                benchmark_instrument_id,
            ),
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["backtest_id"] == str(backtest_id)
    assert body["configuration"]["benchmark_instrument_id"] == str(
        benchmark_instrument_id,
    )
    assert body["configuration"]["training_periods"] == [
        {
            "start_at": "2020-01-01T00:00:00Z",
            "end_at": "2021-01-01T00:00:00Z",
        },
    ]
    assert body["configuration"]["evaluation_periods"] == [
        {
            "start_at": "2021-01-01T00:00:00Z",
            "end_at": "2022-01-01T00:00:00Z",
        },
    ]

    assert persistence.saved_configuration is not None
    assert (
        persistence.saved_configuration.benchmark_instrument_id
        == benchmark_instrument_id
    )


def test_create_backtest_run_remains_compatible_without_configuration(
    monkeypatch,
) -> None:
    persistence = FakePersistenceService()

    monkeypatch.setattr(
        backtest_api,
        "_persistence_service",
        persistence,
    )

    backtest_id = uuid4()

    response = client.post(
        "/backtests/runs",
        json={
            "execution": _execution_payload(backtest_id),
        },
    )

    assert response.status_code == 201
    assert response.json()["configuration"] is None
    assert persistence.saved_configuration is None

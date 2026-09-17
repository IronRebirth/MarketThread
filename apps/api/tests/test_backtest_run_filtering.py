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


class FakePersistenceService:
    def __init__(self) -> None:
        self.received = None

    async def list_runs(
        self,
        session,
        *,
        limit,
        offset,
        valid,
        completed_after,
        completed_before,
    ):
        self.received = {
            "limit": limit,
            "offset": offset,
            "valid": valid,
            "completed_after": completed_after,
            "completed_before": completed_before,
        }

        timestamp = datetime(2026, 1, 2, tzinfo=UTC)

        run = SimpleNamespace(
            id=uuid4(),
            valid=True,
            evaluation_count=5,
            valid_evaluation_count=5,
            rejected_evaluation_count=0,
            configuration=None,
            created_at=timestamp,
            completed_at=timestamp,
        )

        return (run,), 1


def test_list_backtest_runs_passes_filters_to_persistence(monkeypatch) -> None:
    persistence = FakePersistenceService()

    monkeypatch.setattr(
        backtest_api,
        "_persistence_service",
        persistence,
    )

    response = client.get(
        "/backtests/runs",
        params={
            "limit": 10,
            "offset": 20,
            "valid": "true",
            "completed_after": "2026-01-01T00:00:00Z",
            "completed_before": "2026-01-31T23:59:59Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 20

    assert persistence.received is not None
    assert persistence.received["limit"] == 10
    assert persistence.received["offset"] == 20
    assert persistence.received["valid"] is True
    assert persistence.received["completed_after"] == datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )
    assert persistence.received["completed_before"] == datetime(
        2026,
        1,
        31,
        23,
        59,
        59,
        tzinfo=UTC,
    )


def test_list_backtest_runs_accepts_unfiltered_request(monkeypatch) -> None:
    persistence = FakePersistenceService()

    monkeypatch.setattr(
        backtest_api,
        "_persistence_service",
        persistence,
    )

    response = client.get("/backtests/runs")

    assert response.status_code == 200
    assert response.json()["total"] == 1

    assert persistence.received is not None
    assert persistence.received["valid"] is None
    assert persistence.received["completed_after"] is None
    assert persistence.received["completed_before"] is None


def test_list_backtest_runs_rejects_reversed_completion_range() -> None:
    response = client.get(
        "/backtests/runs",
        params={
            "completed_after": "2026-02-01T00:00:00Z",
            "completed_before": "2026-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "completed_after must be earlier than or equal to completed_before."
    )

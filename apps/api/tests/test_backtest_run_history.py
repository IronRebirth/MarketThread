from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.backtesting.api as backtest_api
from app.db.models.backtest import BacktestRun
from app.db.session import get_db_session

api_app = FastAPI()
api_app.include_router(backtest_api.router)


async def override_get_db_session():
    yield object()


api_app.dependency_overrides[get_db_session] = override_get_db_session

client = TestClient(api_app)


def make_run(
    *,
    valid: bool,
    evaluation_count: int,
) -> BacktestRun:
    timestamp = datetime.now(UTC)

    return BacktestRun(
        id=uuid4(),
        valid=valid,
        evaluation_count=evaluation_count,
        valid_evaluation_count=evaluation_count if valid else 0,
        rejected_evaluation_count=0 if valid else evaluation_count,
        configuration=None,
        market_data_expected_count=None,
        market_data_resolved_count=None,
        market_data_coverage_ratio=None,
        market_data_horizon_quality=None,
        notes=[],
        created_at=timestamp,
        completed_at=timestamp,
    )


def test_list_runs_returns_typed_history_response(monkeypatch) -> None:
    newest = make_run(
        valid=True,
        evaluation_count=12,
    )
    older = make_run(
        valid=False,
        evaluation_count=4,
    )

    class FakePersistenceService:
        async def list_runs(
            self,
            session,
            *,
            limit: int,
            offset: int,
            valid: bool | None,
            completed_after: datetime | None,
            completed_before: datetime | None,
        ):
            assert limit == 2
            assert offset == 0
            assert valid is None
            assert completed_after is None
            assert completed_before is None

            return (newest, older), 2

    monkeypatch.setattr(
        backtest_api,
        "_persistence_service",
        FakePersistenceService(),
    )

    response = client.get(
        "/backtests/runs?limit=2&offset=0",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 2
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["runs"]) == 2

    assert body["runs"][0]["backtest_id"] == str(newest.id)
    assert body["runs"][0]["valid"] is True
    assert body["runs"][0]["evaluation_count"] == 12

    assert body["runs"][1]["backtest_id"] == str(older.id)
    assert body["runs"][1]["valid"] is False
    assert body["runs"][1]["evaluation_count"] == 4


def test_list_runs_returns_empty_history_when_no_runs(monkeypatch) -> None:
    class FakePersistenceService:
        async def list_runs(
            self,
            session,
            *,
            limit: int,
            offset: int,
            valid: bool | None,
            completed_after: datetime | None,
            completed_before: datetime | None,
        ):
            assert limit == 20
            assert offset == 0
            assert valid is None
            assert completed_after is None
            assert completed_before is None

            return (), 0

    monkeypatch.setattr(
        backtest_api,
        "_persistence_service",
        FakePersistenceService(),
    )

    response = client.get("/backtests/runs")

    assert response.status_code == 200
    assert response.json() == {
        "runs": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }

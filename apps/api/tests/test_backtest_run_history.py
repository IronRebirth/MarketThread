from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.backtesting.api as backtest_api
from app.backtesting.persistence import BacktestPersistenceService
from app.backtesting.schemas import BacktestRunResponse
from app.db.session import get_db_session
from app.db.models.backtest import BacktestRun


test_app = FastAPI()
test_app.include_router(backtest_api.router)


async def override_get_db_session():
    yield object()


test_app.dependency_overrides[get_db_session] = override_get_db_session

client = TestClient(test_app)


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
        ):
            assert limit == 2
            assert offset == 0
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


def test_list_runs_rejects_invalid_pagination() -> None:
    response = client.get(
        "/backtests/runs?limit=0&offset=-1",
    )

    assert response.status_code == 422


async def test_list_runs_returns_empty_when_offset_exceeds_total() -> None:
    service = BacktestPersistenceService()

    class EmptyResult:
        def scalar_one(self):
            return 0

    class FakeSession:
        async def execute(self, statement):
            return EmptyResult()

    runs, total = await service.list_runs(
        FakeSession(),
        limit=20,
        offset=0,
    )

    assert runs == ()
    assert total == 0
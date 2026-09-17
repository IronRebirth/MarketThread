from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.backtesting.api as backtest_api
from app.backtesting.persistence import BacktestRunNotFoundError
from app.db.models.backtest import BacktestEvaluation
from app.db.session import get_db_session

api_app = FastAPI()
api_app.include_router(backtest_api.router)


async def override_get_db_session():
    yield object()


api_app.dependency_overrides[get_db_session] = override_get_db_session

client = TestClient(api_app)


def make_evaluation() -> BacktestEvaluation:
    timestamp = datetime.now(UTC)

    return BacktestEvaluation(
        id=uuid4(),
        fold_id=uuid4(),
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=uuid4(),
        signal_created_at=timestamp,
        status="valid",
        temporal_error=None,
        signal_direction="up",
        observed_direction="up",
        signal_strength="strong",
        recommendation_state="opportunity",
        signal_confidence=0.82,
        horizon="5d",
        forward_return_pct=2.5,
        benchmark_return_pct=1.0,
        relative_return_pct=1.5,
        direction_correct=True,
        notes=["Evaluation completed successfully."],
    )


class FakePersistenceService:
    async def get_run(self, session, backtest_id):
        return object()

    async def list_evaluations(
        self,
        session,
        backtest_id,
        *,
        limit,
        offset,
    ):
        evaluation = make_evaluation()

        return ((evaluation, 2),), 1


class MissingRunPersistenceService:
    async def get_run(self, session, backtest_id):
        raise BacktestRunNotFoundError(
            f"Backtest run {backtest_id} was not found.",
        )


def test_list_backtest_evaluations_returns_typed_records(monkeypatch) -> None:
    monkeypatch.setattr(
        backtest_api,
        "_persistence_service",
        FakePersistenceService(),
    )

    backtest_id = uuid4()

    response = client.get(
        f"/backtests/runs/{backtest_id}/evaluations?limit=50&offset=0",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["evaluations"]) == 1

    evaluation = body["evaluations"][0]

    assert evaluation["fold_number"] == 2
    assert evaluation["status"] == "valid"
    assert evaluation["signal_direction"] == "up"
    assert evaluation["observed_direction"] == "up"
    assert evaluation["signal_strength"] == "strong"
    assert evaluation["recommendation_state"] == "opportunity"
    assert evaluation["signal_confidence"] == 0.82
    assert evaluation["horizon"] == "5d"
    assert evaluation["forward_return_pct"] == 2.5
    assert evaluation["benchmark_return_pct"] == 1.0
    assert evaluation["relative_return_pct"] == 1.5
    assert evaluation["direction_correct"] is True
    assert evaluation["notes"] == ["Evaluation completed successfully."]


def test_list_backtest_evaluations_returns_404_for_missing_run(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        backtest_api,
        "_persistence_service",
        MissingRunPersistenceService(),
    )

    backtest_id = uuid4()

    response = client.get(
        f"/backtests/runs/{backtest_id}/evaluations",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (f"Backtest run {backtest_id} was not found.")


def test_list_backtest_evaluations_rejects_invalid_pagination() -> None:
    response = client.get(
        f"/backtests/runs/{uuid4()}/evaluations?limit=0&offset=-1",
    )

    assert response.status_code == 422

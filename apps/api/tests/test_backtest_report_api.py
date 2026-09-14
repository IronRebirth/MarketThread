from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.backtesting.api import router

UTC = UTC

app = FastAPI()
app.include_router(router)

client = TestClient(app)


def test_builds_performance_report_from_execution() -> None:
    instrument_id = str(uuid4())
    signal_id = str(uuid4())
    event_id = str(uuid4())
    backtest_id = str(uuid4())

    payload = {
        "execution": {
            "backtest_id": backtest_id,
            "fold_results": [
                {
                    "fold_number": 1,
                    "training_periods": [
                        {
                            "start_at": "2020-01-01T00:00:00Z",
                            "end_at": "2021-01-01T00:00:00Z",
                        }
                    ],
                    "evaluation_periods": [
                        {
                            "start_at": "2021-01-01T00:00:00Z",
                            "end_at": "2022-01-01T00:00:00Z",
                        }
                    ],
                    "valid": True,
                    "evaluations": [
                        {
                            "signal_id": signal_id,
                            "event_id": event_id,
                            "instrument_id": instrument_id,
                            "signal_created_at": (
                                datetime(
                                    2021,
                                    2,
                                    1,
                                    tzinfo=UTC,
                                ).isoformat()
                            ),
                            "status": "valid",
                            "signal_direction": "positive",
                            "observed_direction": "positive",
                            "signal_strength": "strong",
                            "recommendation_state": "consider",
                            "signal_confidence": 0.9,
                            "horizon": "1d",
                            "forward_return_pct": 5.0,
                            "benchmark_return_pct": 1.0,
                            "relative_return_pct": 4.0,
                            "direction_correct": True,
                            "notes": [],
                        }
                    ],
                }
            ],
            "valid": True,
            "evaluation_count": 1,
            "valid_evaluation_count": 1,
            "rejected_evaluation_count": 0,
            "notes": [],
        }
    }

    response = client.post(
        "/backtests/performance-report",
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["backtest_id"] == backtest_id
    assert body["total_evaluations"] == 1
    assert body["valid_evaluations"] == 1
    assert body["average_forward_return_pct"] == 5.0
    assert body["average_relative_return_pct"] == 4.0


def test_empty_execution_returns_insufficient_evidence() -> None:
    payload = {
        "execution": {
            "backtest_id": str(uuid4()),
            "fold_results": [],
            "valid": False,
            "evaluation_count": 0,
            "valid_evaluation_count": 0,
            "rejected_evaluation_count": 0,
            "notes": [],
        }
    }

    response = client.post(
        "/backtests/performance-report",
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total_evaluations"] == 0
    assert body["quality_state"] == "insufficient_evidence"
    assert "no_evaluations" in body["quality_warnings"]


def test_invalid_execution_payload_returns_validation_error() -> None:
    response = client.post(
        "/backtests/performance-report",
        json={
            "execution": {
                "backtest_id": "not-a-uuid",
            }
        },
    )

    assert response.status_code == 422


def test_report_contains_horizon_breakdown() -> None:
    instrument_id = str(uuid4())

    payload = {
        "execution": {
            "backtest_id": str(uuid4()),
            "fold_results": [
                {
                    "fold_number": 1,
                    "training_periods": [
                        {
                            "start_at": "2020-01-01T00:00:00Z",
                            "end_at": "2021-01-01T00:00:00Z",
                        }
                    ],
                    "evaluation_periods": [
                        {
                            "start_at": "2021-01-01T00:00:00Z",
                            "end_at": "2022-01-01T00:00:00Z",
                        }
                    ],
                    "valid": True,
                    "evaluations": [
                        {
                            "signal_id": str(uuid4()),
                            "event_id": str(uuid4()),
                            "instrument_id": instrument_id,
                            "signal_created_at": "2021-02-01T00:00:00Z",
                            "status": "valid",
                            "signal_direction": "positive",
                            "observed_direction": "positive",
                            "signal_strength": "strong",
                            "recommendation_state": "consider",
                            "signal_confidence": 0.8,
                            "horizon": "5d",
                            "forward_return_pct": 4.0,
                            "benchmark_return_pct": 1.0,
                            "relative_return_pct": 3.0,
                            "direction_correct": True,
                            "notes": [],
                        }
                    ],
                }
            ],
            "valid": True,
            "evaluation_count": 1,
            "valid_evaluation_count": 1,
            "rejected_evaluation_count": 0,
            "notes": [],
        }
    }

    response = client.post(
        "/backtests/performance-report",
        json=payload,
    )

    assert response.status_code == 200

    summaries = response.json()["by_horizon"]["summaries"]

    assert len(summaries) == 3
    assert any(
        item["state"] == "5d" and item["evaluation_count"] == 1 for item in summaries
    )

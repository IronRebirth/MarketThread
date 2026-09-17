from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.backtesting.api as backtest_api
from app.provenance.models import (
    AnalysisStage,
    EvidenceReference,
    ProvenanceRecord,
)
from app.provenance.persistence import ProvenanceNotFoundError

app = FastAPI()
app.include_router(backtest_api.router)

client = TestClient(app)


def make_provenance() -> ProvenanceRecord:
    timestamp = datetime.now(UTC)

    return ProvenanceRecord(
        result_id=uuid4(),
        stage=AnalysisStage.BACKTESTING,
        created_at=timestamp,
        ruleset_version="1.0.0",
        evidence=(
            EvidenceReference(
                article_id=uuid4(),
                source_name="Example Financial News",
                source_url="https://example.com/article",
                published_at=timestamp,
                discovered_at=timestamp,
                retrieved_at=timestamp,
                relevance_note="Primary source supporting the historical analysis.",
            ),
        ),
        input_ids=(uuid4(), uuid4()),
        assumptions=("Historical observations remain unchanged.",),
        invalidation_conditions=("The execution ruleset changes.",),
    )


class FakeProvenancePersistenceService:
    def __init__(self, record: ProvenanceRecord) -> None:
        self.record = record

    async def get(
        self,
        session,
        result_id,
    ) -> ProvenanceRecord:
        return self.record


class MissingProvenancePersistenceService:
    async def get(
        self,
        session,
        result_id,
    ) -> ProvenanceRecord:
        raise ProvenanceNotFoundError(
            f"Provenance for result {result_id} was not found.",
        )


def test_get_backtest_provenance_returns_typed_response(monkeypatch) -> None:
    record = make_provenance()

    monkeypatch.setattr(
        backtest_api,
        "_provenance_persistence_service",
        FakeProvenancePersistenceService(record),
    )

    response = client.get(
        f"/backtests/runs/{record.result_id}/provenance",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["result_id"] == str(record.result_id)
    assert body["stage"] == "backtesting"
    assert body["ruleset_version"] == "1.0.0"
    assert body["input_ids"] == [str(input_id) for input_id in record.input_ids]
    assert body["assumptions"] == list(record.assumptions)
    assert body["invalidation_conditions"] == list(
        record.invalidation_conditions,
    )

    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["article_id"] == str(
        record.evidence[0].article_id,
    )
    assert body["evidence"][0]["source_name"] == "Example Financial News"


def test_get_backtest_provenance_returns_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        backtest_api,
        "_provenance_persistence_service",
        MissingProvenancePersistenceService(),
    )

    backtest_id = uuid4()

    response = client.get(
        f"/backtests/runs/{backtest_id}/provenance",
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == f"Provenance for result {backtest_id} was not found."
    )

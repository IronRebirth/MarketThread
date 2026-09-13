from datetime import UTC, datetime
from uuid import uuid4

from app.provenance.models import (
    AnalysisStage,
    EvidenceReference,
)
from app.provenance.service import ProvenanceService


def make_evidence() -> EvidenceReference:
    """Create source evidence for provenance tests."""

    timestamp = datetime.now(UTC)

    return EvidenceReference(
        article_id=uuid4(),
        source_name="Example Financial News",
        source_url="https://example.com/article",
        published_at=timestamp,
        discovered_at=timestamp,
        retrieved_at=timestamp,
        relevance_note="Primary source supporting the market event.",
    )


def test_creates_provenance_record() -> None:
    result_id = uuid4()
    input_ids = (uuid4(),)
    evidence = (make_evidence(),)

    record = ProvenanceService().create_record(
        result_id=result_id,
        stage=AnalysisStage.RECOMMENDATION,
        input_ids=input_ids,
        evidence=evidence,
        assumptions=("The event remains materially relevant.",),
        invalidation_conditions=("The event is reversed.",),
    )

    assert record.result_id == result_id
    assert record.stage == AnalysisStage.RECOMMENDATION
    assert record.ruleset_version == "1.0.0"
    assert record.input_ids == input_ids
    assert record.evidence == evidence
    assert record.assumptions == ("The event remains materially relevant.",)
    assert record.invalidation_conditions == ("The event is reversed.",)


def test_supports_multiple_evidence_references() -> None:
    evidence = (
        make_evidence(),
        make_evidence(),
    )

    record = ProvenanceService().create_record(
        result_id=uuid4(),
        stage=AnalysisStage.EVENT_INTELLIGENCE,
        input_ids=(uuid4(), uuid4()),
        evidence=evidence,
        assumptions=(),
        invalidation_conditions=(),
    )

    assert len(record.evidence) == 2


def test_custom_ruleset_version_is_preserved() -> None:
    record = ProvenanceService().create_record(
        result_id=uuid4(),
        stage=AnalysisStage.SIGNAL_INTELLIGENCE,
        input_ids=(),
        evidence=(),
        assumptions=(),
        invalidation_conditions=(),
        ruleset_version="1.1.0",
    )

    assert record.ruleset_version == "1.1.0"


def test_created_at_is_timezone_aware() -> None:
    record = ProvenanceService().create_record(
        result_id=uuid4(),
        stage=AnalysisStage.RISK_CONFIDENCE,
        input_ids=(),
        evidence=(),
        assumptions=(),
        invalidation_conditions=(),
    )

    assert record.created_at.tzinfo is not None
    assert record.created_at.utcoffset() is not None

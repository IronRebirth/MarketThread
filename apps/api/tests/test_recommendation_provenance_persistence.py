from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from app.db.models.instrument import Instrument
from app.db.models.recommendation import RecommendationRecord
from app.db.models.recommendation_provenance import (
    RecommendationProvenanceRecord,
)
from app.db.models.signal import SignalRecord
from app.recommendations.models import RecommendationState
from app.recommendations.provenance import RecommendationProvenance
from app.recommendations.provenance_persistence import (
    RecommendationProvenancePersistenceService,
)


def make_recommendation(
    *,
    signal_id: UUID,
    event_id: UUID,
    ticker: str,
) -> RecommendationRecord:
    return RecommendationRecord(
        id=uuid4(),
        signal_id=signal_id,
        event_id=event_id,
        company_name="Test Company",
        ticker=ticker,
        created_at=datetime.now(UTC),
        state=RecommendationState.CONSIDER.value,
        signal_direction="positive",
        confidence_score=0.84,
        risk_score=0.16,
        confidence_level="high",
        risk_level="low",
        time_horizon="medium_term",
        supporting_factors=["Demand remains strong."],
        contradicting_factors=[],
        assumptions=[
            "The identified market event remains materially relevant.",
        ],
        invalidation_conditions=["Underlying event is reversed."],
        evidence_article_ids=[str(uuid4())],
        rationale="Research-oriented recommendation assessment.",
    )


@pytest.mark.asyncio
async def test_provenance_persistence_is_idempotent(
    db_session,
) -> None:
    signal_id = uuid4()
    event_id = uuid4()
    market_impact_id = uuid4()
    ticker = f"RVP{uuid4().hex[:8].upper()}"

    instrument = Instrument(
        symbol=ticker,
        name="Test Company",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    signal_record = SignalRecord(
        id=signal_id,
        market_impact_id=None,
        event_id=event_id,
        instrument_id=instrument.id,
        company_name="Test Company",
        ticker=ticker,
        created_at=datetime.now(UTC),
        direction="positive",
        strength="strong",
        opportunity="opportunity",
        confidence=0.84,
        risk_score=0.16,
        time_horizon="medium_term",
        supporting_factors=["Demand remains strong."],
        contradicting_factors=[],
        evidence_article_ids=[str(uuid4())],
        invalidation_conditions=["Underlying event is reversed."],
        rationale="Persisted test signal.",
    )
    db_session.add(signal_record)
    await db_session.flush()

    recommendation = make_recommendation(
        signal_id=signal_id,
        event_id=event_id,
        ticker=ticker,
    )
    db_session.add(recommendation)
    await db_session.commit()
    await db_session.refresh(recommendation)

    evidence_article_id = UUID(recommendation.evidence_article_ids[0])
    created_at = recommendation.created_at

    provenance = RecommendationProvenance(
        recommendation_id=recommendation.id,
        signal_id=signal_id,
        market_impact_id=market_impact_id,
        event_id=event_id,
        created_at=created_at,
        ruleset_version="1.0.0",
        input_ids=(signal_id, market_impact_id, event_id),
        evidence_article_ids=(evidence_article_id,),
        assumptions=tuple(recommendation.assumptions),
        invalidation_conditions=tuple(
            recommendation.invalidation_conditions,
        ),
    )

    service = RecommendationProvenancePersistenceService()

    try:
        first = await service.create(
            db_session,
            provenance=provenance,
            created_at=created_at,
        )
        second = await service.create(
            db_session,
            provenance=provenance,
            created_at=created_at,
        )

        restored = await service.get_by_recommendation_id(
            db_session,
            recommendation.id,
        )

        assert first.id == second.id
        assert restored is not None
        assert service.to_domain(restored) == provenance
    finally:
        await db_session.execute(
            delete(RecommendationProvenanceRecord).where(
                RecommendationProvenanceRecord.recommendation_id == recommendation.id,
            ),
        )
        await db_session.execute(
            delete(RecommendationRecord).where(
                RecommendationRecord.id == recommendation.id,
            ),
        )
        await db_session.execute(
            delete(SignalRecord).where(
                SignalRecord.id == signal_id,
            ),
        )
        await db_session.execute(
            delete(Instrument).where(
                Instrument.id == instrument.id,
            ),
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_provenance_missing_returns_none(
    db_session,
) -> None:
    provenance = await (
        RecommendationProvenancePersistenceService().get_by_recommendation_id(
            db_session,
            uuid4(),
        )
    )

    assert provenance is None

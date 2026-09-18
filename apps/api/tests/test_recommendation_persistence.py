from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.db.models.instrument import Instrument
from app.db.models.recommendation import RecommendationRecord
from app.db.models.signal import SignalRecord
from app.recommendations.models import Recommendation, RecommendationState
from app.recommendations.persistence import RecommendationPersistenceService


def make_recommendation(ticker: str) -> Recommendation:
    return Recommendation(
        event_id=uuid4(),
        company_name="NVIDIA",
        ticker=ticker,
        state=RecommendationState.CONSIDER,
        signal_direction="positive",
        confidence_score=0.84,
        risk_score=0.16,
        confidence_level="high",
        risk_level="low",
        time_horizon="medium_term",
        supporting_factors=("Demand remains strong.",),
        contradicting_factors=(),
        assumptions=("The identified market event remains materially relevant.",),
        invalidation_conditions=("Underlying event is reversed.",),
        evidence_article_ids=(uuid4(),),
        rationale="Research-oriented recommendation assessment.",
    )


async def create_persisted_signal(
    db_session,
    *,
    signal_id,
    recommendation: Recommendation,
) -> UUID:
    instrument = Instrument(
        symbol=recommendation.ticker,
        name="NVIDIA",
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
        event_id=recommendation.event_id,
        instrument_id=instrument.id,
        company_name=recommendation.company_name,
        ticker=recommendation.ticker,
        created_at=datetime.now(UTC),
        direction="positive",
        strength="strong",
        opportunity="opportunity",
        confidence=recommendation.confidence_score,
        risk_score=recommendation.risk_score,
        time_horizon=recommendation.time_horizon,
        supporting_factors=list(recommendation.supporting_factors),
        contradicting_factors=list(recommendation.contradicting_factors),
        evidence_article_ids=[
            str(article_id) for article_id in recommendation.evidence_article_ids
        ],
        invalidation_conditions=list(
            recommendation.invalidation_conditions,
        ),
        rationale="Persisted test signal.",
    )
    db_session.add(signal_record)

    await db_session.commit()

    return instrument.id


@pytest.mark.asyncio
async def test_recommendation_persistence_is_idempotent(
    db_session,
) -> None:
    signal_id = uuid4()
    ticker = f"RCP{uuid4().hex[:8].upper()}"
    recommendation = make_recommendation(ticker)

    service = RecommendationPersistenceService()

    instrument_id = await create_persisted_signal(
        db_session,
        signal_id=signal_id,
        recommendation=recommendation,
    )

    try:
        created_at = datetime.now(UTC).replace(microsecond=0)

        first = await service.create(
            db_session,
            recommendation=recommendation,
            signal_id=signal_id,
            created_at=created_at,
        )
        second = await service.create(
            db_session,
            recommendation=recommendation,
            signal_id=signal_id,
            created_at=created_at,
        )

        records = (
            (
                await db_session.execute(
                    select(RecommendationRecord).where(
                        RecommendationRecord.signal_id == signal_id,
                    ),
                )
            )
            .scalars()
            .all()
        )

        assert first.id == second.id
        assert len(records) == 1
        assert first.company_name == "NVIDIA"
        assert first.ticker == ticker
        assert first.state == "consider"
        assert first.evidence_article_ids
    finally:
        await db_session.execute(
            delete(RecommendationRecord).where(
                RecommendationRecord.signal_id == signal_id,
            ),
        )
        await db_session.execute(
            delete(SignalRecord).where(
                SignalRecord.id == signal_id,
            ),
        )
        await db_session.execute(
            delete(Instrument).where(
                Instrument.id == instrument_id,
            ),
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_recommendation_persistence_get_and_list(
    db_session,
) -> None:
    signal_id = uuid4()
    ticker = f"RCP{uuid4().hex[:8].upper()}"
    recommendation = make_recommendation(ticker)

    service = RecommendationPersistenceService()

    instrument_id = await create_persisted_signal(
        db_session,
        signal_id=signal_id,
        recommendation=recommendation,
    )

    try:
        created = await service.create(
            db_session,
            recommendation=recommendation,
            signal_id=signal_id,
            created_at=datetime.now(UTC),
        )

        fetched = await service.get(
            db_session,
            created.id,
        )
        records = await service.list(
            db_session,
            signal_id=signal_id,
            ticker=ticker.lower(),
        )

        assert fetched.id == created.id
        assert records == (created,)
    finally:
        await db_session.execute(
            delete(RecommendationRecord).where(
                RecommendationRecord.signal_id == signal_id,
            ),
        )
        await db_session.execute(
            delete(SignalRecord).where(
                SignalRecord.id == signal_id,
            ),
        )
        await db_session.execute(
            delete(Instrument).where(
                Instrument.id == instrument_id,
            ),
        )
        await db_session.commit()

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select

from app.db.models.instrument import Instrument
from app.db.models.signal import SignalRecord
from app.signals.models import (
    MarketSignal,
    SignalDirection,
    SignalOpportunity,
    SignalStrength,
)
from app.signals.persistence import (
    SignalNotFoundError,
    SignalPersistenceService,
)

persistence_service = SignalPersistenceService()


def build_signal() -> MarketSignal:
    """Build a representative market signal for persistence tests."""

    return MarketSignal(
        event_id=uuid4(),
        company_name="Apple Inc.",
        ticker="AAPL",
        direction=SignalDirection.POSITIVE,
        strength=SignalStrength.STRONG,
        opportunity=SignalOpportunity.OPPORTUNITY,
        confidence=0.86,
        risk_score=0.31,
        time_horizon="medium_term",
        supporting_factors=(
            "Strong positive event impact",
            "Supportive market evidence",
        ),
        contradicting_factors=("Elevated valuation risk",),
        evidence_article_ids=(uuid4(), uuid4()),
        invalidation_conditions=(
            "Event thesis materially reverses",
            "Market response contradicts the expected direction",
        ),
        rationale="The event has a strong positive expected impact on the company.",
    )


async def create_instrument(db_session, *, symbol: str) -> Instrument:
    """Create a temporary instrument used by signal persistence tests."""

    instrument = Instrument(
        symbol=symbol,
        name="Apple Inc.",
        exchange="NASDAQ",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


async def cleanup_instrument(db_session, instrument_id) -> None:
    """Remove signal and instrument records created by a test."""

    await db_session.execute(
        delete(SignalRecord).where(
            SignalRecord.instrument_id == instrument_id,
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.id == instrument_id,
        ),
    )
    await db_session.commit()


async def test_signal_persistence_create_get_and_list(db_session):
    """Persist, retrieve, and filter a market signal snapshot."""

    instrument = await create_instrument(
        db_session,
        symbol=f"TST{uuid4().hex[:8].upper()}",
    )
    signal = build_signal()
    created_at = datetime(
        2026,
        9,
        14,
        10,
        30,
        tzinfo=UTC,
    )

    try:
        record = await persistence_service.create(
            db_session,
            signal=signal,
            instrument_id=instrument.id,
            created_at=created_at,
        )

        assert record.id is not None
        assert record.event_id == signal.event_id
        assert record.instrument_id == instrument.id
        assert record.company_name == signal.company_name
        assert record.ticker == signal.ticker
        assert record.created_at == created_at
        assert record.direction == signal.direction.value
        assert record.strength == signal.strength.value
        assert record.opportunity == signal.opportunity.value
        assert record.confidence == signal.confidence
        assert record.risk_score == signal.risk_score
        assert record.time_horizon == signal.time_horizon
        assert record.supporting_factors == list(signal.supporting_factors)
        assert record.contradicting_factors == list(
            signal.contradicting_factors,
        )
        assert record.evidence_article_ids == [
            str(article_id) for article_id in signal.evidence_article_ids
        ]
        assert record.invalidation_conditions == list(
            signal.invalidation_conditions,
        )
        assert record.rationale == signal.rationale

        retrieved = await persistence_service.get(
            db_session,
            record.id,
        )

        assert retrieved.id == record.id
        assert retrieved.event_id == signal.event_id
        assert retrieved.instrument_id == instrument.id

        records = await persistence_service.list(
            db_session,
            instrument_id=instrument.id,
            start_at=datetime(
                2026,
                9,
                14,
                10,
                0,
                tzinfo=UTC,
            ),
            end_at=datetime(
                2026,
                9,
                14,
                11,
                0,
                tzinfo=UTC,
            ),
        )

        assert len(records) == 1
        assert records[0].id == record.id
    finally:
        await cleanup_instrument(db_session, instrument.id)


async def test_signal_persistence_missing_signal_raises(db_session):
    """Raise a domain-specific error when a signal does not exist."""

    missing_signal_id = uuid4()

    try:
        await persistence_service.get(
            db_session,
            missing_signal_id,
        )
    except SignalNotFoundError as exc:
        assert str(missing_signal_id) in str(exc)
    else:
        raise AssertionError("Expected SignalNotFoundError.")


async def test_signal_api_create_get_and_list(client, db_session):
    """Persist a signal through HTTP and retrieve it through the API."""

    instrument = await create_instrument(
        db_session,
        symbol=f"TST{uuid4().hex[:8].upper()}",
    )
    signal = build_signal()
    created_at = datetime(
        2026,
        9,
        14,
        12,
        0,
        tzinfo=UTC,
    )

    payload = {
        "instrument_id": str(instrument.id),
        "created_at": created_at.isoformat(),
        **signal.model_dump(mode="json"),
    }

    try:
        create_response = await client.post(
            "/signals",
            json=payload,
        )

        assert create_response.status_code == 201

        created = create_response.json()

        assert created["signal_id"]
        assert created["instrument_id"] == str(instrument.id)
        assert created["event_id"] == str(signal.event_id)
        assert created["company_name"] == signal.company_name
        assert created["ticker"] == signal.ticker
        assert created["direction"] == signal.direction.value
        assert created["strength"] == signal.strength.value
        assert created["opportunity"] == signal.opportunity.value
        assert created["confidence"] == signal.confidence
        assert created["risk_score"] == signal.risk_score
        assert created["time_horizon"] == signal.time_horizon
        assert created["supporting_factors"] == list(
            signal.supporting_factors,
        )
        assert created["contradicting_factors"] == list(
            signal.contradicting_factors,
        )
        assert created["evidence_article_ids"] == [
            str(article_id) for article_id in signal.evidence_article_ids
        ]
        assert created["invalidation_conditions"] == list(
            signal.invalidation_conditions,
        )
        assert created["rationale"] == signal.rationale

        signal_id = created["signal_id"]

        get_response = await client.get(
            f"/signals/{signal_id}",
        )

        assert get_response.status_code == 200
        assert get_response.json() == created

        list_response = await client.get(
            "/signals",
            params={
                "instrument_id": str(instrument.id),
                "limit": 100,
            },
        )

        assert list_response.status_code == 200

        listed = list_response.json()

        assert len(listed) == 1
        assert listed[0]["signal_id"] == signal_id
    finally:
        await db_session.execute(
            delete(SignalRecord).where(
                SignalRecord.instrument_id == instrument.id,
            ),
        )

        result = await db_session.execute(
            select(Instrument).where(
                Instrument.id == instrument.id,
            ),
        )
        created_instrument = result.scalar_one_or_none()

        if created_instrument is not None:
            await db_session.delete(created_instrument)

        await db_session.commit()

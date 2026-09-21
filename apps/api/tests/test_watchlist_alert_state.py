from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord
from app.db.models.instrument import Instrument
from app.db.models.market_impact import MarketImpactRecord
from app.db.models.watchlist_alert_state import WatchlistAlertStateRecord


async def create_authenticated_user(
    client: AsyncClient,
) -> tuple[str, str]:
    email = f"alert-state-test-{uuid4().hex}@example.com"
    password = "StrongPassword123"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code == 201

    login_response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    return email, login_response.cookies["marketthread.access"]


async def create_test_instrument(
    db_session: AsyncSession,
    *,
    symbol: str | None = None,
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=symbol or f"ASTATE-{uuid4().hex[:8].upper()}",
        name="Alert State Test Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


async def create_market_impact(
    db_session: AsyncSession,
    *,
    ticker: str,
    first_seen_at: datetime,
) -> tuple[EventRecord, CompanyImpactRecord, MarketImpactRecord]:
    event = EventRecord(
        id=uuid4(),
        deduplication_key=f"alert-state-event-{uuid4().hex}",
        event_type="earnings",
        title="Alert state test event",
        summary="A persisted event used for alert-state tests.",
        catalyst="earnings",
        market_relevance="high",
        impact_direction="positive",
        affected_entities=["Alert State Test Company"],
        affected_sectors=["technology"],
        source_article_ids=[],
        first_seen_at=first_seen_at,
        last_seen_at=first_seen_at,
        confidence=0.9,
    )

    db_session.add(event)
    await db_session.flush()

    company_impact = CompanyImpactRecord(
        id=uuid4(),
        event_id=event.id,
        company_name="Alert State Test Company",
        ticker=ticker,
        impact_type="direct",
        direction="positive",
        mechanism="Earnings improve expectations.",
        confidence=0.88,
        evidence_article_ids=[],
        rationale="Alert state test company impact.",
    )

    db_session.add(company_impact)
    await db_session.flush()

    market_impact = MarketImpactRecord(
        id=uuid4(),
        company_impact_id=company_impact.id,
        event_id=event.id,
        company_name=company_impact.company_name,
        ticker=ticker,
        impact_type="direct",
        direction="positive",
        factor="revenue",
        time_horizon="short_term",
        confidence=0.86,
        evidence_article_ids=[],
        rationale="Alert state test market impact.",
    )

    db_session.add(market_impact)

    await db_session.commit()

    await db_session.refresh(event)
    await db_session.refresh(company_impact)
    await db_session.refresh(market_impact)

    return event, company_impact, market_impact


async def count_alert_states(
    db_session: AsyncSession,
    *,
    watchlist_id,
) -> int:
    result = await db_session.scalar(
        select(func.count(WatchlistAlertStateRecord.alert_id)).where(
            WatchlistAlertStateRecord.watchlist_id == watchlist_id,
        ),
    )

    return int(result or 0)


@pytest.mark.asyncio
async def test_alert_state_requires_authentication(
    client: AsyncClient,
) -> None:
    watchlist_id = uuid4()
    alert_id = uuid4()

    get_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
    )

    assert get_response.status_code == 401

    patch_response = await client.patch(
        f"/watchlists/{watchlist_id}/alerts/{alert_id}/state",
        json={"status": "seen"},
    )

    assert patch_response.status_code == 401


@pytest.mark.asyncio
async def test_first_alert_read_materializes_new_state(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": f"State New {uuid4().hex[:8]}"},
        headers=headers,
    )

    assert watchlist_response.status_code == 201

    watchlist_id = watchlist_response.json()["watchlist_id"]

    item_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert item_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
        first_seen_at=datetime.now(UTC),
    )

    response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["alert_count"] == 1
    assert body["returned_alert_count"] == 1
    assert len(body["alerts"]) == 1

    alert = body["alerts"][0]

    assert alert["status"] == "new"
    assert alert["seen_at"] is None
    assert alert["acknowledged_at"] is None

    state_count = await count_alert_states(
        db_session,
        watchlist_id=watchlist_id,
    )

    assert state_count == 1


@pytest.mark.asyncio
async def test_repeated_alert_reads_are_deduplicated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": f"State Repeat {uuid4().hex[:8]}"},
        headers=headers,
    )

    assert watchlist_response.status_code == 201

    watchlist_id = watchlist_response.json()["watchlist_id"]

    item_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert item_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
        first_seen_at=datetime.now(UTC),
    )

    first_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    second_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_alert = first_response.json()["alerts"][0]
    second_alert = second_response.json()["alerts"][0]

    assert first_alert["alert_id"] == second_alert["alert_id"]
    assert first_alert["status"] == "new"
    assert second_alert["status"] == "new"

    state_count = await count_alert_states(
        db_session,
        watchlist_id=watchlist_id,
    )

    assert state_count == 1


@pytest.mark.asyncio
async def test_seen_state_persists_and_records_timestamp(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": f"State Seen {uuid4().hex[:8]}"},
        headers=headers,
    )

    assert watchlist_response.status_code == 201

    watchlist_id = watchlist_response.json()["watchlist_id"]

    item_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert item_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
        first_seen_at=datetime.now(UTC),
    )

    alert_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    assert alert_response.status_code == 200

    alert_id = alert_response.json()["alerts"][0]["alert_id"]

    transition_response = await client.patch(
        f"/watchlists/{watchlist_id}/alerts/{alert_id}/state",
        json={"status": "seen"},
        headers=headers,
    )

    assert transition_response.status_code == 200

    transition_body = transition_response.json()

    assert transition_body["status"] == "seen"
    assert transition_body["seen_at"] is not None
    assert transition_body["acknowledged_at"] is None

    repeated_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    assert repeated_response.status_code == 200

    repeated_alert = repeated_response.json()["alerts"][0]

    assert repeated_alert["alert_id"] == alert_id
    assert repeated_alert["status"] == "seen"
    assert repeated_alert["seen_at"] is not None
    assert repeated_alert["acknowledged_at"] is None


@pytest.mark.asyncio
async def test_acknowledgement_records_both_lifecycle_timestamps(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": f"State Ack {uuid4().hex[:8]}"},
        headers=headers,
    )

    assert watchlist_response.status_code == 201

    watchlist_id = watchlist_response.json()["watchlist_id"]

    item_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert item_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
        first_seen_at=datetime.now(UTC),
    )

    alert_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    alert_id = alert_response.json()["alerts"][0]["alert_id"]

    acknowledge_response = await client.patch(
        f"/watchlists/{watchlist_id}/alerts/{alert_id}/state",
        json={"status": "acknowledged"},
        headers=headers,
    )

    assert acknowledge_response.status_code == 200

    body = acknowledge_response.json()

    assert body["status"] == "acknowledged"
    assert body["seen_at"] is not None
    assert body["acknowledged_at"] is not None

    get_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    assert get_response.status_code == 200

    alert = get_response.json()["alerts"][0]

    assert alert["status"] == "acknowledged"
    assert alert["seen_at"] is not None
    assert alert["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_backward_alert_state_transition_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": f"State Backward {uuid4().hex[:8]}"},
        headers=headers,
    )

    assert watchlist_response.status_code == 201

    watchlist_id = watchlist_response.json()["watchlist_id"]

    item_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert item_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
        first_seen_at=datetime.now(UTC),
    )

    alert_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    alert_id = alert_response.json()["alerts"][0]["alert_id"]

    seen_response = await client.patch(
        f"/watchlists/{watchlist_id}/alerts/{alert_id}/state",
        json={"status": "seen"},
        headers=headers,
    )

    assert seen_response.status_code == 200

    backward_response = await client.patch(
        f"/watchlists/{watchlist_id}/alerts/{alert_id}/state",
        json={"status": "new"},
        headers=headers,
    )

    assert backward_response.status_code == 422

    assert (
        "Cannot move alert from seen back to new."
        in (backward_response.json()["detail"])
    )


@pytest.mark.asyncio
async def test_acknowledged_alert_cannot_return_to_seen(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": f"State Ack Back {uuid4().hex[:8]}"},
        headers=headers,
    )

    assert watchlist_response.status_code == 201

    watchlist_id = watchlist_response.json()["watchlist_id"]

    item_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert item_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
        first_seen_at=datetime.now(UTC),
    )

    alert_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    alert_id = alert_response.json()["alerts"][0]["alert_id"]

    acknowledge_response = await client.patch(
        f"/watchlists/{watchlist_id}/alerts/{alert_id}/state",
        json={"status": "acknowledged"},
        headers=headers,
    )

    assert acknowledge_response.status_code == 200

    backward_response = await client.patch(
        f"/watchlists/{watchlist_id}/alerts/{alert_id}/state",
        json={"status": "seen"},
        headers=headers,
    )

    assert backward_response.status_code == 422

    assert (
        "Cannot move alert from acknowledged back to seen."
        in backward_response.json()["detail"]
    )


@pytest.mark.asyncio
async def test_other_user_cannot_update_alert_state(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    owner_headers = {
        "Authorization": f"Bearer {owner_token}",
    }
    other_headers = {
        "Authorization": f"Bearer {other_token}",
    }

    instrument = await create_test_instrument(db_session)

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": f"State Owner {uuid4().hex[:8]}"},
        headers=owner_headers,
    )

    assert watchlist_response.status_code == 201

    watchlist_id = watchlist_response.json()["watchlist_id"]

    item_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=owner_headers,
    )

    assert item_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
        first_seen_at=datetime.now(UTC),
    )

    alert_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=owner_headers,
    )

    assert alert_response.status_code == 200

    alert_id = alert_response.json()["alerts"][0]["alert_id"]

    response = await client.patch(
        f"/watchlists/{watchlist_id}/alerts/{alert_id}/state",
        json={"status": "seen"},
        headers=other_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_same_alert_can_be_acknowledged_directly_from_new(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": f"State Direct Ack {uuid4().hex[:8]}"},
        headers=headers,
    )

    assert watchlist_response.status_code == 201

    watchlist_id = watchlist_response.json()["watchlist_id"]

    item_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert item_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
        first_seen_at=datetime.now(UTC),
    )

    alert_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    alert_id = alert_response.json()["alerts"][0]["alert_id"]

    acknowledge_response = await client.patch(
        f"/watchlists/{watchlist_id}/alerts/{alert_id}/state",
        json={"status": "acknowledged"},
        headers=headers,
    )

    assert acknowledge_response.status_code == 200

    body = acknowledge_response.json()

    assert body["status"] == "acknowledged"
    assert body["seen_at"] is not None
    assert body["acknowledged_at"] is not None

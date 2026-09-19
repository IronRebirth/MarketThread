from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord
from app.db.models.instrument import Instrument
from app.db.models.market_impact import MarketImpactRecord
from app.db.models.user import User


async def create_authenticated_user(
    client: AsyncClient,
) -> tuple[str, str]:
    email = f"watchlist-alerts-{uuid4().hex}@example.com"
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

    return email, login_response.json()["access_token"]


async def create_test_instrument(
    db_session: AsyncSession,
    *,
    symbol: str | None = None,
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=symbol or f"ALERTTEST-{uuid4().hex[:8].upper()}",
        name="Watchlist Alert Test Instrument",
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
        deduplication_key=f"alert-event-{uuid4().hex}",
        event_type="corporate_event",
        title="Test market-moving event",
        summary="Test event summary.",
        catalyst="earnings",
        market_relevance="high",
        impact_direction="positive",
        affected_entities=[ticker],
        affected_sectors=["technology"],
        source_article_ids=[],
        first_seen_at=first_seen_at,
        last_seen_at=first_seen_at,
        confidence=0.90,
    )

    db_session.add(event)
    await db_session.flush()

    company_impact = CompanyImpactRecord(
        id=uuid4(),
        event_id=event.id,
        company_name="Alert Test Company",
        ticker=ticker,
        impact_type="direct",
        direction="positive",
        mechanism="Test mechanism.",
        confidence=0.85,
        evidence_article_ids=[],
        rationale="Test company impact rationale.",
    )

    db_session.add(company_impact)
    await db_session.flush()

    market_impact = MarketImpactRecord(
        id=uuid4(),
        company_impact_id=company_impact.id,
        event_id=event.id,
        company_name="Alert Test Company",
        ticker=ticker,
        impact_type="direct",
        direction="positive",
        factor="earnings",
        time_horizon="short_term",
        confidence=0.80,
        evidence_article_ids=[],
        rationale="Test market impact rationale.",
    )

    db_session.add(market_impact)
    await db_session.commit()
    await db_session.refresh(event)
    await db_session.refresh(company_impact)
    await db_session.refresh(market_impact)

    return event, company_impact, market_impact


@pytest.fixture(autouse=True)
async def clean_watchlist_alert_test_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("watchlist-alerts-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("ALERTTEST-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_watchlist_alerts_require_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/watchlists/{uuid4()}/alerts",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_watchlist_has_no_alerts(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/watchlists",
        json={"name": "Empty Alerts"},
        headers=headers,
    )

    assert create_response.status_code == 201

    watchlist_id = create_response.json()["watchlist_id"]

    response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "empty"
    assert body["item_count"] == 0
    assert body["matched_item_count"] == 0
    assert body["unmatched_item_count"] == 0
    assert body["alert_count"] == 0
    assert body["returned_alert_count"] == 0
    assert body["alerts"] == []


@pytest.mark.asyncio
async def test_matching_new_market_impact_produces_alert(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(
        db_session,
        symbol="ALERTTEST-ABC",
    )

    create_response = await client.post(
        "/watchlists",
        json={"name": "Alert Feed"},
        headers=headers,
    )

    assert create_response.status_code == 201

    watchlist_id = create_response.json()["watchlist_id"]

    add_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert add_response.status_code == 201

    item_added_at = datetime.fromisoformat(
        add_response.json()["added_at"],
    )
    assessment_time = item_added_at + timedelta(seconds=5)
    event_time = item_added_at + timedelta(seconds=1)

    event, company_impact, market_impact = await create_market_impact(
        db_session,
        ticker=" alerttest-abc ",
        first_seen_at=event_time,
    )

    response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        params={
            "assessed_at": assessment_time.isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"
    assert body["item_count"] == 1
    assert body["matched_item_count"] == 1
    assert body["unmatched_item_count"] == 0
    assert body["alert_count"] == 1
    assert body["returned_alert_count"] == 1

    alert = body["alerts"][0]

    assert alert["watchlist_id"] == watchlist_id
    assert alert["watchlist_item_id"] == add_response.json()["item_id"]
    assert alert["instrument_id"] == str(instrument.id)

    assert alert["symbol"] == "ALERTTEST-ABC"
    assert alert["ticker"] == "ALERTTEST-ABC"

    assert alert["event_id"] == str(event.id)
    assert alert["company_impact_id"] == str(company_impact.id)
    assert alert["market_impact_id"] == str(market_impact.id)

    assert alert["event_type"] == "corporate_event"
    assert alert["direction"] == "positive"
    assert alert["impact_type"] == "direct"

    alert_added_at = datetime.fromisoformat(
        alert["watchlist_item_added_at"],
    )
    alert_first_seen_at = datetime.fromisoformat(
        alert["first_seen_at"],
    )

    assert alert_added_at <= alert_first_seen_at < assessment_time
    assert "does not predict" in alert["explanation"]


@pytest.mark.asyncio
async def test_older_event_does_not_alert_after_watchlist_item_is_added(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(
        db_session,
        symbol="ALERTTEST-OLD",
    )

    create_response = await client.post(
        "/watchlists",
        json={"name": "Old Intelligence"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    old_time = datetime.now(UTC) - timedelta(days=1)

    await create_market_impact(
        db_session,
        ticker="ALERTTEST-OLD",
        first_seen_at=old_time,
    )

    add_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert add_response.status_code == 201

    response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "none"
    assert body["alert_count"] == 0
    assert body["returned_alert_count"] == 0
    assert body["matched_item_count"] == 0
    assert body["unmatched_item_count"] == 1
    assert body["alerts"] == []


@pytest.mark.asyncio
async def test_non_matching_ticker_does_not_alert(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(
        db_session,
        symbol="ALERTTEST-MATCH",
    )

    create_response = await client.post(
        "/watchlists",
        json={"name": "Ticker Isolation"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    add_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert add_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker="ALERTTEST-OTHER",
        first_seen_at=datetime.now(UTC),
    )

    response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["alert_count"] == 0
    assert body["matched_item_count"] == 0
    assert body["unmatched_item_count"] == 1


@pytest.mark.asyncio
async def test_alert_identity_is_stable_across_repeated_reads(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(
        db_session,
        symbol="ALERTTEST-STABLE",
    )

    create_response = await client.post(
        "/watchlists",
        json={"name": "Stable Alerts"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    add_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert add_response.status_code == 201

    item_added_at = datetime.fromisoformat(
        add_response.json()["added_at"],
    )
    assessment_time = item_added_at + timedelta(seconds=5)

    _, _, market_impact = await create_market_impact(
        db_session,
        ticker="ALERTTEST-STABLE",
        first_seen_at=item_added_at + timedelta(seconds=1),
    )

    first_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        params={
            "assessed_at": assessment_time.isoformat(),
        },
        headers=headers,
    )
    second_response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        params={
            "assessed_at": assessment_time.isoformat(),
        },
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_alert = first_response.json()["alerts"][0]
    second_alert = second_response.json()["alerts"][0]

    assert first_alert["alert_id"] == second_alert["alert_id"]
    assert first_alert["market_impact_id"] == str(market_impact.id)

    assert UUID(first_alert["alert_id"])


@pytest.mark.asyncio
async def test_multiple_alerts_are_limited_without_changing_total_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(
        db_session,
        symbol="ALERTTEST-LIMIT",
    )

    create_response = await client.post(
        "/watchlists",
        json={"name": "Limited Alerts"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    add_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert add_response.status_code == 201

    item_added_at = datetime.fromisoformat(
        add_response.json()["added_at"],
    )
    base_time = item_added_at + timedelta(seconds=1)
    assessment_time = base_time + timedelta(seconds=10)

    for offset in range(3):
        await create_market_impact(
            db_session,
            ticker="ALERTTEST-LIMIT",
            first_seen_at=base_time + timedelta(seconds=offset),
        )

    response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        params={
            "limit": 2,
            "assessed_at": assessment_time.isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["alert_count"] == 3
    assert body["returned_alert_count"] == 2
    assert len(body["alerts"]) == 2


@pytest.mark.asyncio
async def test_watchlist_alerts_enforce_ownership(
    client: AsyncClient,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    create_response = await client.post(
        "/watchlists",
        json={"name": "Private Alerts"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert create_response.status_code == 201

    watchlist_id = create_response.json()["watchlist_id"]

    response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_watchlist_alert_limit_is_validated(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/watchlists",
        json={"name": "Alert Validation"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    response = await client.get(
        f"/watchlists/{watchlist_id}/alerts",
        params={"limit": 0},
        headers=headers,
    )

    assert response.status_code == 422

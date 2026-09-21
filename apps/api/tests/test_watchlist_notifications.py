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
from app.db.models.watchlist_notification import WatchlistNotificationRecord


async def create_authenticated_user(
    client: AsyncClient,
) -> tuple[str, str]:
    email = f"notification-test-{uuid4().hex}@example.com"
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
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=f"ANOT-{uuid4().hex[:8].upper()}",
        name="Notification Test Instrument",
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
) -> MarketImpactRecord:
    timestamp = datetime.now(UTC)

    event = EventRecord(
        id=uuid4(),
        deduplication_key=f"notification-event-{uuid4().hex}",
        event_type="earnings",
        title="Notification test event",
        summary="A persisted event used for notification tests.",
        catalyst="earnings",
        market_relevance="high",
        impact_direction="positive",
        affected_entities=["Notification Test Company"],
        affected_sectors=["technology"],
        source_article_ids=[],
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.91,
    )

    db_session.add(event)
    await db_session.flush()

    company_impact = CompanyImpactRecord(
        id=uuid4(),
        event_id=event.id,
        company_name="Notification Test Company",
        ticker=ticker,
        impact_type="direct",
        direction="positive",
        mechanism="Earnings improve expectations.",
        confidence=0.89,
        evidence_article_ids=[],
        rationale="Notification test company impact.",
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
        confidence=0.87,
        evidence_article_ids=[],
        rationale="Notification test market impact.",
    )

    db_session.add(market_impact)
    await db_session.commit()
    await db_session.refresh(market_impact)

    return market_impact


async def create_watchlist_with_rule(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    headers: dict[str, str],
    rule_name: str,
    enabled: bool = True,
) -> tuple[str, Instrument]:
    instrument = await create_test_instrument(db_session)

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": f"Notifications {uuid4().hex[:8]}"},
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

    rule_response = await client.post(
        f"/watchlists/{watchlist_id}/alert-rules",
        json={
            "name": rule_name,
            "conditions": {
                "event_types": ["earnings"],
                "directions": ["positive"],
                "minimum_confidence": 0.8,
            },
            "enabled": enabled,
        },
        headers=headers,
    )

    assert rule_response.status_code == 201

    return watchlist_id, instrument


async def count_notifications(
    db_session: AsyncSession,
    *,
    user_id,
) -> int:
    result = await db_session.scalar(
        select(func.count(WatchlistNotificationRecord.id)).where(
            WatchlistNotificationRecord.user_id == user_id,
        ),
    )

    return int(result or 0)


@pytest.mark.asyncio
async def test_notifications_require_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get("/notifications")

    assert response.status_code == 401

    sync_response = await client.post("/notifications/sync")

    assert sync_response.status_code == 401


@pytest.mark.asyncio
async def test_sync_materializes_matching_alert_as_notification(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    watchlist_id, instrument = await create_watchlist_with_rule(
        client,
        db_session,
        headers=headers,
        rule_name="Positive earnings",
    )

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
    )

    response = await client.post(
        "/notifications/sync",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "created_count": 1,
        "existing_count": 0,
        "matched_alert_count": 1,
    }

    list_response = await client.get(
        "/notifications",
        headers=headers,
    )

    assert list_response.status_code == 200

    body = list_response.json()

    assert body["returned_count"] == 1
    assert body["unread_count"] == 1
    assert len(body["notifications"]) == 1

    notification = body["notifications"][0]

    assert notification["watchlist_id"] == watchlist_id
    assert notification["symbol"] == instrument.symbol
    assert notification["rule_name"] == "Positive earnings"
    assert notification["event_type"] == "earnings"
    assert notification["direction"] == "positive"
    assert notification["read_at"] is None

    assert (
        await count_notifications(
            db_session,
            user_id=(await client.get("/auth/me", headers=headers)).json()["id"],
        )
        == 1
    )


@pytest.mark.asyncio
async def test_repeated_sync_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    _, instrument = await create_watchlist_with_rule(
        client,
        db_session,
        headers=headers,
        rule_name="Repeated notification",
    )

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
    )

    first_response = await client.post(
        "/notifications/sync",
        headers=headers,
    )
    second_response = await client.post(
        "/notifications/sync",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert first_response.json()["created_count"] == 1
    assert second_response.json()["created_count"] == 0
    assert second_response.json()["existing_count"] == 1

    list_response = await client.get(
        "/notifications",
        headers=headers,
    )

    assert list_response.json()["returned_count"] == 1


@pytest.mark.asyncio
async def test_one_alert_can_create_one_notification_per_matching_rule(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    watchlist_id, instrument = await create_watchlist_with_rule(
        client,
        db_session,
        headers=headers,
        rule_name="Rule one",
    )

    second_rule_response = await client.post(
        f"/watchlists/{watchlist_id}/alert-rules",
        json={
            "name": "Rule two",
            "conditions": {
                "event_types": ["earnings"],
            },
        },
        headers=headers,
    )

    assert second_rule_response.status_code == 201

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
    )

    sync_response = await client.post(
        "/notifications/sync",
        headers=headers,
    )

    assert sync_response.status_code == 200
    assert sync_response.json()["created_count"] == 2
    assert sync_response.json()["matched_alert_count"] == 1

    list_response = await client.get(
        "/notifications",
        headers=headers,
    )

    body = list_response.json()

    assert body["returned_count"] == 2
    assert body["unread_count"] == 2
    assert {item["rule_name"] for item in body["notifications"]} == {
        "Rule one",
        "Rule two",
    }


@pytest.mark.asyncio
async def test_disabled_rule_does_not_materialize_notification(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    _, instrument = await create_watchlist_with_rule(
        client,
        db_session,
        headers=headers,
        rule_name="Disabled rule",
        enabled=False,
    )

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
    )

    response = await client.post(
        "/notifications/sync",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["created_count"] == 0
    assert response.json()["matched_alert_count"] == 0

    list_response = await client.get(
        "/notifications",
        headers=headers,
    )

    assert list_response.json()["returned_count"] == 0


@pytest.mark.asyncio
async def test_mark_notification_read_persists_and_updates_unread_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    _, instrument = await create_watchlist_with_rule(
        client,
        db_session,
        headers=headers,
        rule_name="Read notification",
    )

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
    )

    await client.post(
        "/notifications/sync",
        headers=headers,
    )

    list_response = await client.get(
        "/notifications",
        headers=headers,
    )

    notification_id = list_response.json()["notifications"][0]["notification_id"]

    read_response = await client.patch(
        f"/notifications/{notification_id}/read",
        headers=headers,
    )

    assert read_response.status_code == 200
    assert read_response.json()["notification"]["read_at"] is not None

    repeated_response = await client.get(
        "/notifications",
        headers=headers,
    )

    assert repeated_response.json()["unread_count"] == 0
    assert repeated_response.json()["notifications"][0]["read_at"] is not None

    unread_response = await client.get(
        "/notifications?unread_only=true",
        headers=headers,
    )

    assert unread_response.status_code == 200
    assert unread_response.json()["returned_count"] == 0


@pytest.mark.asyncio
async def test_other_user_cannot_mark_notification_read(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    _, instrument = await create_watchlist_with_rule(
        client,
        db_session,
        headers=owner_headers,
        rule_name="Ownership notification",
    )

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
    )

    await client.post(
        "/notifications/sync",
        headers=owner_headers,
    )

    list_response = await client.get(
        "/notifications",
        headers=owner_headers,
    )

    notification_id = list_response.json()["notifications"][0]["notification_id"]

    response = await client.patch(
        f"/notifications/{notification_id}/read",
        headers=other_headers,
    )

    assert response.status_code == 404

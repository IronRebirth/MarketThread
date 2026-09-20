from datetime import datetime, UTC
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.watchlists.alert_rule_models import (
    AlertRuleType,
    WatchlistAlertRule,
    WatchlistAlertRuleConditions,
)
from app.watchlists.alert_rules import WatchlistAlertRuleService
from app.watchlists.alerts_models import WatchlistAlert


async def create_authenticated_user(
    client: AsyncClient,
) -> str:
    email = f"watchlist-alert-rule-{uuid4().hex}@example.com"
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

    return login_response.json()["access_token"]


@pytest.fixture(autouse=True)
async def clean_watchlist_alert_rule_test_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("watchlist-alert-rule-%@example.com"),
        ),
    )
    await db_session.commit()


def build_alert(
    *,
    event_type: str = "regulatory_action",
    direction: str = "negative",
    confidence: float = 0.80,
    event_confidence: float = 0.90,
) -> WatchlistAlert:
    now = datetime.now(UTC)

    return WatchlistAlert(
        alert_id=uuid4(),
        watchlist_id=uuid4(),
        watchlist_item_id=uuid4(),
        instrument_id=uuid4(),
        symbol="TEST",
        company_name="Test Company",
        ticker="TEST",
        market_impact_id=uuid4(),
        company_impact_id=uuid4(),
        event_id=uuid4(),
        event_type=event_type,
        title="Test alert",
        summary="Test alert summary",
        catalyst="regulation",
        market_relevance="high",
        event_impact_direction=direction,
        impact_type="direct",
        direction=direction,
        factor="regulatory_action",
        time_horizon="short_term",
        confidence=confidence,
        event_confidence=event_confidence,
        watchlist_item_added_at=now,
        first_seen_at=now,
        last_seen_at=now,
        source_article_ids=(),
        rationale="Test rationale",
        explanation="Test explanation",
    )


def build_rule(
    *,
    rule_id: UUID | None = None,
    enabled: bool = True,
    event_types: tuple[str, ...] = (),
    directions: tuple[str, ...] = (),
    minimum_confidence: float | None = None,
    minimum_event_confidence: float | None = None,
) -> WatchlistAlertRule:
    now = datetime.now(UTC)

    return WatchlistAlertRule(
        rule_id=rule_id or uuid4(),
        watchlist_id=uuid4(),
        name="Test rule",
        rule_type=AlertRuleType.EVENT_IMPACT,
        conditions=WatchlistAlertRuleConditions(
            event_types=event_types,
            directions=directions,
            minimum_confidence=minimum_confidence,
            minimum_event_confidence=minimum_event_confidence,
        ),
        enabled=enabled,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_alert_rules_require_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/watchlists/{uuid4()}/alert-rules",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_and_list_alert_rule(
    client: AsyncClient,
) -> None:
    token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": "Rule Feed"},
        headers=headers,
    )

    assert watchlist_response.status_code == 201

    watchlist_id = watchlist_response.json()["watchlist_id"]

    create_response = await client.post(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=headers,
        json={
            "name": "High confidence regulatory events",
            "conditions": {
                "event_types": [" Regulatory_Action "],
                "directions": ["Negative"],
                "minimum_confidence": 0.70,
                "minimum_event_confidence": 0.80,
            },
        },
    )

    assert create_response.status_code == 201

    created = create_response.json()

    assert created["watchlist_id"] == watchlist_id
    assert created["name"] == "High confidence regulatory events"
    assert created["rule_type"] == "event_impact"
    assert created["enabled"] is True
    assert created["conditions"]["event_types"] == ["regulatory_action"]
    assert created["conditions"]["directions"] == ["negative"]
    assert created["conditions"]["minimum_confidence"] == 0.70
    assert created["conditions"]["minimum_event_confidence"] == 0.80

    list_response = await client.get(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert list_response.json() == [created]


@pytest.mark.asyncio
async def test_duplicate_rule_name_is_rejected_by_database_constraint(
    client: AsyncClient,
) -> None:
    token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": "Unique Rules"},
        headers=headers,
    )

    watchlist_id = watchlist_response.json()["watchlist_id"]

    payload = {
        "name": "Duplicate rule",
        "conditions": {},
    }

    first = await client.post(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=headers,
        json=payload,
    )
    second = await client.post(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_update_alert_rule(
    client: AsyncClient,
) -> None:
    token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": "Update Rules"},
        headers=headers,
    )

    watchlist_id = watchlist_response.json()["watchlist_id"]

    create_response = await client.post(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=headers,
        json={
            "name": "Initial rule",
            "conditions": {},
        },
    )

    rule_id = create_response.json()["rule_id"]

    update_response = await client.patch(
        f"/watchlists/{watchlist_id}/alert-rules/{rule_id}",
        headers=headers,
        json={
            "name": "Updated rule",
            "enabled": False,
            "conditions": {
                "directions": ["positive"],
                "minimum_confidence": 0.75,
            },
        },
    )

    assert update_response.status_code == 200

    body = update_response.json()

    assert body["rule_id"] == rule_id
    assert body["name"] == "Updated rule"
    assert body["enabled"] is False
    assert body["conditions"]["directions"] == ["positive"]
    assert body["conditions"]["minimum_confidence"] == 0.75


@pytest.mark.asyncio
async def test_empty_update_is_rejected(
    client: AsyncClient,
) -> None:
    token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": "Empty Patch"},
        headers=headers,
    )

    watchlist_id = watchlist_response.json()["watchlist_id"]

    create_response = await client.post(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=headers,
        json={"name": "Rule"},
    )

    rule_id = create_response.json()["rule_id"]

    response = await client.patch(
        f"/watchlists/{watchlist_id}/alert-rules/{rule_id}",
        headers=headers,
        json={},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_other_user_cannot_read_or_mutate_rule(
    client: AsyncClient,
) -> None:
    owner_token = await create_authenticated_user(client)
    other_token = await create_authenticated_user(client)

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": "Private Rules"},
        headers=owner_headers,
    )

    watchlist_id = watchlist_response.json()["watchlist_id"]

    create_response = await client.post(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=owner_headers,
        json={"name": "Private rule"},
    )

    rule_id = create_response.json()["rule_id"]

    list_response = await client.get(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=other_headers,
    )
    update_response = await client.patch(
        f"/watchlists/{watchlist_id}/alert-rules/{rule_id}",
        headers=other_headers,
        json={"enabled": False},
    )
    delete_response = await client.delete(
        f"/watchlists/{watchlist_id}/alert-rules/{rule_id}",
        headers=other_headers,
    )

    assert list_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_alert_rule(
    client: AsyncClient,
) -> None:
    token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    watchlist_response = await client.post(
        "/watchlists",
        json={"name": "Delete Rules"},
        headers=headers,
    )

    watchlist_id = watchlist_response.json()["watchlist_id"]

    create_response = await client.post(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=headers,
        json={"name": "Rule to delete"},
    )

    rule_id = create_response.json()["rule_id"]

    delete_response = await client.delete(
        f"/watchlists/{watchlist_id}/alert-rules/{rule_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    list_response = await client.get(
        f"/watchlists/{watchlist_id}/alert-rules",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert list_response.json() == []


def test_rule_matches_all_event_impact_alerts_when_unfiltered() -> None:
    alert = build_alert()
    rule = build_rule()

    assert WatchlistAlertRuleService.matches(
        alert=alert,
        rule=rule,
    )


def test_rule_matches_configured_filters_case_insensitively() -> None:
    alert = build_alert(
        event_type="Regulatory_Action",
        direction="Negative",
        confidence=0.82,
        event_confidence=0.94,
    )
    rule = build_rule(
        event_types=("REGULATORY_ACTION",),
        directions=("NEGATIVE",),
        minimum_confidence=0.80,
        minimum_event_confidence=0.90,
    )

    assert WatchlistAlertRuleService.matches(
        alert=alert,
        rule=rule,
    )


def test_rule_rejects_alert_below_any_threshold() -> None:
    alert = build_alert(
        confidence=0.60,
        event_confidence=0.95,
    )
    rule = build_rule(
        minimum_confidence=0.70,
        minimum_event_confidence=0.90,
    )

    assert not WatchlistAlertRuleService.matches(
        alert=alert,
        rule=rule,
    )


def test_disabled_rule_never_matches() -> None:
    alert = build_alert()
    rule = build_rule(enabled=False)

    assert not WatchlistAlertRuleService.matches(
        alert=alert,
        rule=rule,
    )


def test_select_matching_alerts_uses_or_semantics() -> None:
    matching_alert = build_alert(
        event_type="earnings_surprise",
        direction="positive",
    )
    unmatched_alert = build_alert(
        event_type="regulatory_action",
        direction="negative",
    )

    rules = (
        build_rule(
            event_types=("earnings_surprise",),
            directions=("positive",),
        ),
        build_rule(
            event_types=("cyberattack",),
        ),
    )

    selected = WatchlistAlertRuleService.select_matching_alerts(
        alerts=(matching_alert, unmatched_alert),
        rules=rules,
    )

    assert selected == (matching_alert,)


def test_select_matching_alerts_returns_none_without_enabled_rules() -> None:
    alert = build_alert()
    rule = build_rule(enabled=False)

    selected = WatchlistAlertRuleService.select_matching_alerts(
        alerts=(alert,),
        rules=(rule,),
    )

    assert selected == ()

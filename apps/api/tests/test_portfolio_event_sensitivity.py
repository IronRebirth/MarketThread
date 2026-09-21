from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord
from app.db.models.instrument import Instrument
from app.db.models.market_impact import MarketImpactRecord
from app.db.models.portfolio import (
    PortfolioPositionRecord,
    PortfolioRecord,
)
from app.db.models.portfolio_history import (
    PortfolioPositionHistoryRecord,
)

TEST_PASSWORD = "StrongPassword123"


async def create_authenticated_user(
    client: AsyncClient,
) -> str:
    """Create and authenticate a test user."""

    email = f"portfolio-event-sensitivity-{uuid4().hex}@example.com"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert register_response.status_code == 201

    login_response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    return login_response.cookies["marketthread.access"]


async def create_instrument(
    db_session: AsyncSession,
    *,
    symbol: str,
    exchange: str = "TEST",
) -> Instrument:
    """Create a deterministic active test instrument."""

    instrument = Instrument(
        id=uuid4(),
        symbol=symbol,
        name="Event Sensitivity Test Instrument",
        exchange=exchange,
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


async def create_portfolio(
    client: AsyncClient,
    token: str,
    *,
    name: str,
) -> str:
    """Create a portfolio through the public portfolio API."""

    response = await client.post(
        "/portfolios",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201

    return response.json()["portfolio_id"]


async def add_position(
    client: AsyncClient,
    *,
    token: str,
    portfolio_id: str,
    instrument_id,
) -> None:
    """Add a current position through the existing portfolio API."""

    response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument_id}",
        json={
            "quantity": "10",
            "average_cost": "100",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


async def seed_market_impact(
    db_session: AsyncSession,
    *,
    ticker: str,
    title: str,
    first_seen_at: datetime,
) -> tuple:
    """Persist an event, company impact, and market impact for testing."""

    event_id = uuid4()
    company_impact_id = uuid4()
    market_impact_id = uuid4()
    article_id = uuid4()

    event = EventRecord(
        id=event_id,
        deduplication_key=f"event-sensitivity-{uuid4().hex}",
        event_type="trade_policy",
        title=title,
        summary="A persisted market event affects the test company.",
        catalyst="tariff",
        market_relevance="high",
        impact_direction="negative",
        affected_entities=["Test Company"],
        affected_sectors=["Technology"],
        source_article_ids=[str(article_id)],
        first_seen_at=first_seen_at,
        last_seen_at=first_seen_at,
        confidence=0.84,
    )

    company_impact = CompanyImpactRecord(
        id=company_impact_id,
        event_id=event_id,
        company_name="Test Company",
        ticker=ticker,
        impact_type="direct",
        direction="negative",
        mechanism="Potential exposure through market access.",
        confidence=0.84,
        evidence_article_ids=[str(article_id)],
        rationale="The company has direct exposure to the event.",
    )

    market_impact = MarketImpactRecord(
        id=market_impact_id,
        company_impact_id=company_impact_id,
        event_id=event_id,
        company_name="Test Company",
        ticker=ticker,
        impact_type="direct",
        direction="negative",
        factor="market_access",
        time_horizon="medium_term",
        confidence=0.84,
        evidence_article_ids=[str(article_id)],
        rationale="Potential market-access pressure may affect the company.",
    )

    # Persist parent rows explicitly because these SQLAlchemy models do not
    # expose ORM relationships that establish dependency ordering.
    db_session.add(event)
    await db_session.flush()

    db_session.add(company_impact)
    await db_session.flush()

    db_session.add(market_impact)
    await db_session.commit()

    return (
        event_id,
        company_impact_id,
        market_impact_id,
    )


async def cleanup_portfolio(
    db_session: AsyncSession,
    *,
    portfolio_id: str,
    instrument_ids,
) -> None:
    """Remove portfolio test state in foreign-key-safe order."""

    await db_session.execute(
        delete(PortfolioPositionHistoryRecord).where(
            PortfolioPositionHistoryRecord.portfolio_id == portfolio_id,
        ),
    )
    await db_session.execute(
        delete(PortfolioPositionRecord).where(
            PortfolioPositionRecord.portfolio_id == portfolio_id,
        ),
    )
    await db_session.execute(
        delete(PortfolioRecord).where(
            PortfolioRecord.id == portfolio_id,
        ),
    )

    if instrument_ids:
        await db_session.execute(
            delete(Instrument).where(
                Instrument.id.in_(instrument_ids),
            ),
        )

    await db_session.commit()


async def cleanup_market_intelligence(
    db_session: AsyncSession,
    *,
    event_ids,
    company_impact_ids,
    market_impact_ids,
) -> None:
    """Remove seeded event intelligence."""

    if market_impact_ids:
        await db_session.execute(
            delete(MarketImpactRecord).where(
                MarketImpactRecord.id.in_(market_impact_ids),
            ),
        )

    if company_impact_ids:
        await db_session.execute(
            delete(CompanyImpactRecord).where(
                CompanyImpactRecord.id.in_(company_impact_ids),
            ),
        )

    if event_ids:
        await db_session.execute(
            delete(EventRecord).where(
                EventRecord.id.in_(event_ids),
            ),
        )

    await db_session.commit()


@pytest.mark.asyncio
async def test_empty_portfolio_returns_empty_sensitivity(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token = await create_authenticated_user(client)

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Event Empty {uuid4().hex[:8]}",
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/event-sensitivity",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "empty"
    assert body["position_count"] == 0
    assert body["matched_position_count"] == 0
    assert body["unmatched_position_count"] == 0
    assert body["event_count"] == 0
    assert body["impact_count"] == 0
    assert body["returned_impact_count"] == 0
    assert body["unmatched_symbols"] == []
    assert body["items"] == []

    await cleanup_portfolio(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[],
    )


@pytest.mark.asyncio
async def test_exact_ticker_match_returns_event_impact_and_evidence(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token = await create_authenticated_user(client)

    symbol = f"EVTSEN{uuid4().hex[:8].upper()}"

    instrument = await create_instrument(
        db_session,
        symbol=symbol,
    )

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Event Match {uuid4().hex[:8]}",
    )

    await add_position(
        client,
        token=token,
        portfolio_id=portfolio_id,
        instrument_id=instrument.id,
    )

    event_ids = []
    company_impact_ids = []
    market_impact_ids = []

    (
        event_id,
        company_impact_id,
        market_impact_id,
    ) = await seed_market_impact(
        db_session,
        ticker=f"  {symbol.lower()}  ",
        title="Test tariff event",
        first_seen_at=datetime.now(UTC),
    )

    event_ids.append(event_id)
    company_impact_ids.append(company_impact_id)
    market_impact_ids.append(market_impact_id)

    response = await client.get(
        f"/portfolios/{portfolio_id}/event-sensitivity",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"
    assert body["position_count"] == 1
    assert body["matched_position_count"] == 1
    assert body["unmatched_position_count"] == 0
    assert body["event_count"] == 1
    assert body["impact_count"] == 1
    assert body["returned_impact_count"] == 1
    assert body["unmatched_symbols"] == []

    item = body["items"][0]

    assert item["position"]["symbol"] == symbol
    assert item["ticker"] == symbol.lower().strip()
    assert item["company_name"] == "Test Company"
    assert item["impact_type"] == "direct"
    assert item["direction"] == "negative"
    assert item["factor"] == "market_access"
    assert item["time_horizon"] == "medium_term"
    assert item["confidence"] == pytest.approx(0.84)
    assert item["event_type"] == "trade_policy"
    assert item["title"] == "Test tariff event"
    assert item["catalyst"] == "tariff"
    assert item["market_relevance"] == "high"
    assert item["event_impact_direction"] == "negative"
    assert len(item["source_article_ids"]) == 1
    assert item["event_confidence"] == pytest.approx(0.84)

    await cleanup_market_intelligence(
        db_session,
        event_ids=event_ids,
        company_impact_ids=company_impact_ids,
        market_impact_ids=market_impact_ids,
    )

    await cleanup_portfolio(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_partial_matching_reports_unmatched_positions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token = await create_authenticated_user(client)

    matched_symbol = f"EVTP{uuid4().hex[:8].upper()}"
    unmatched_symbol = f"EVTN{uuid4().hex[:8].upper()}"

    matched_instrument = await create_instrument(
        db_session,
        symbol=matched_symbol,
    )
    unmatched_instrument = await create_instrument(
        db_session,
        symbol=unmatched_symbol,
    )

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Event Partial {uuid4().hex[:8]}",
    )

    await add_position(
        client,
        token=token,
        portfolio_id=portfolio_id,
        instrument_id=matched_instrument.id,
    )

    await add_position(
        client,
        token=token,
        portfolio_id=portfolio_id,
        instrument_id=unmatched_instrument.id,
    )

    event_ids = []
    company_impact_ids = []
    market_impact_ids = []

    (
        event_id,
        company_impact_id,
        market_impact_id,
    ) = await seed_market_impact(
        db_session,
        ticker=matched_symbol,
        title="Partial event",
        first_seen_at=datetime.now(UTC),
    )

    event_ids.append(event_id)
    company_impact_ids.append(company_impact_id)
    market_impact_ids.append(market_impact_id)

    response = await client.get(
        f"/portfolios/{portfolio_id}/event-sensitivity",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "partial"
    assert body["position_count"] == 2
    assert body["matched_position_count"] == 1
    assert body["unmatched_position_count"] == 1
    assert body["unmatched_symbols"] == [unmatched_symbol]
    assert len(body["items"]) == 1

    await cleanup_market_intelligence(
        db_session,
        event_ids=event_ids,
        company_impact_ids=company_impact_ids,
        market_impact_ids=market_impact_ids,
    )

    await cleanup_portfolio(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[
            matched_instrument.id,
            unmatched_instrument.id,
        ],
    )


@pytest.mark.asyncio
async def test_no_matching_impact_returns_none_quality(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token = await create_authenticated_user(client)

    portfolio_symbol = f"EVTNO{uuid4().hex[:8].upper()}"
    unrelated_symbol = f"EVTOTHER{uuid4().hex[:8].upper()}"

    instrument = await create_instrument(
        db_session,
        symbol=portfolio_symbol,
    )

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Event None {uuid4().hex[:8]}",
    )

    await add_position(
        client,
        token=token,
        portfolio_id=portfolio_id,
        instrument_id=instrument.id,
    )

    event_ids = []
    company_impact_ids = []
    market_impact_ids = []

    (
        event_id,
        company_impact_id,
        market_impact_id,
    ) = await seed_market_impact(
        db_session,
        ticker=unrelated_symbol,
        title="Unrelated event",
        first_seen_at=datetime.now(UTC),
    )

    event_ids.append(event_id)
    company_impact_ids.append(company_impact_id)
    market_impact_ids.append(market_impact_id)

    response = await client.get(
        f"/portfolios/{portfolio_id}/event-sensitivity",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "none"
    assert body["position_count"] == 1
    assert body["matched_position_count"] == 0
    assert body["unmatched_position_count"] == 1
    assert body["event_count"] == 0
    assert body["impact_count"] == 0
    assert body["returned_impact_count"] == 0
    assert body["unmatched_symbols"] == [portfolio_symbol]
    assert body["items"] == []

    await cleanup_market_intelligence(
        db_session,
        event_ids=event_ids,
        company_impact_ids=company_impact_ids,
        market_impact_ids=market_impact_ids,
    )

    await cleanup_portfolio(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_limit_truncates_items_but_preserves_total_counts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token = await create_authenticated_user(client)

    symbol = f"EVTLIM{uuid4().hex[:8].upper()}"

    instrument = await create_instrument(
        db_session,
        symbol=symbol,
    )

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Event Limit {uuid4().hex[:8]}",
    )

    await add_position(
        client,
        token=token,
        portfolio_id=portfolio_id,
        instrument_id=instrument.id,
    )

    event_ids = []
    company_impact_ids = []
    market_impact_ids = []

    for index in range(3):
        (
            event_id,
            company_impact_id,
            market_impact_id,
        ) = await seed_market_impact(
            db_session,
            ticker=symbol,
            title=f"Limited event {index}",
            first_seen_at=datetime.now(UTC) + timedelta(minutes=index),
        )

        event_ids.append(event_id)
        company_impact_ids.append(company_impact_id)
        market_impact_ids.append(market_impact_id)

    response = await client.get(
        f"/portfolios/{portfolio_id}/event-sensitivity",
        params={"limit": 2},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"
    assert body["position_count"] == 1
    assert body["matched_position_count"] == 1
    assert body["event_count"] == 3
    assert body["impact_count"] == 3
    assert body["returned_impact_count"] == 2
    assert len(body["items"]) == 2
    assert any(
        "limited to the first 2 matching impact records" in note.lower()
        for note in body["notes"]
    )

    await cleanup_market_intelligence(
        db_session,
        event_ids=event_ids,
        company_impact_ids=company_impact_ids,
        market_impact_ids=market_impact_ids,
    )

    await cleanup_portfolio(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_duplicate_symbol_across_exchanges_is_treated_as_ambiguous(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token = await create_authenticated_user(client)

    symbol = f"EVTAMB{uuid4().hex[:8].upper()}"

    first_instrument = await create_instrument(
        db_session,
        symbol=symbol,
        exchange="FIRST",
    )

    second_instrument = await create_instrument(
        db_session,
        symbol=symbol,
        exchange="SECOND",
    )

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Event Ambiguous {uuid4().hex[:8]}",
    )

    await add_position(
        client,
        token=token,
        portfolio_id=portfolio_id,
        instrument_id=first_instrument.id,
    )

    await add_position(
        client,
        token=token,
        portfolio_id=portfolio_id,
        instrument_id=second_instrument.id,
    )

    event_ids = []
    company_impact_ids = []
    market_impact_ids = []

    (
        event_id,
        company_impact_id,
        market_impact_id,
    ) = await seed_market_impact(
        db_session,
        ticker=symbol,
        title="Ambiguous symbol event",
        first_seen_at=datetime.now(UTC),
    )

    event_ids.append(event_id)
    company_impact_ids.append(company_impact_id)
    market_impact_ids.append(market_impact_id)

    response = await client.get(
        f"/portfolios/{portfolio_id}/event-sensitivity",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "none"
    assert body["position_count"] == 2
    assert body["matched_position_count"] == 0
    assert body["unmatched_position_count"] == 2
    assert body["unmatched_symbols"] == [symbol]
    assert body["items"] == []
    assert any("ambiguous" in note.lower() for note in body["notes"])

    await cleanup_market_intelligence(
        db_session,
        event_ids=event_ids,
        company_impact_ids=company_impact_ids,
        market_impact_ids=market_impact_ids,
    )

    await cleanup_portfolio(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[
            first_instrument.id,
            second_instrument.id,
        ],
    )


@pytest.mark.asyncio
async def test_other_user_cannot_access_portfolio_event_sensitivity(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_token = await create_authenticated_user(client)
    other_token = await create_authenticated_user(client)

    instrument = await create_instrument(
        db_session,
        symbol=f"EVTOWN{uuid4().hex[:8].upper()}",
    )

    portfolio_id = await create_portfolio(
        client,
        owner_token,
        name=f"Event Ownership {uuid4().hex[:8]}",
    )

    await add_position(
        client,
        token=owner_token,
        portfolio_id=portfolio_id,
        instrument_id=instrument.id,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/event-sensitivity",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404

    await cleanup_portfolio(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_unauthenticated_event_sensitivity_is_rejected(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/portfolios/{uuid4()}/event-sensitivity",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_event_sensitivity_limit_is_validated(
    client: AsyncClient,
) -> None:
    token = await create_authenticated_user(client)

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Event Validation {uuid4().hex[:8]}",
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/event-sensitivity",
        params={"limit": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

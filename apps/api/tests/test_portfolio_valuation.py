from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.models.instrument import Instrument
from app.db.models.market_data import MarketQuote
from app.db.models.user import User


async def create_authenticated_user(
    client: AsyncClient,
) -> tuple[str, str]:
    email = f"portfolio-valuation-{uuid4().hex}@example.com"
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
    db_session,
    *,
    currency: str = "USD",
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=f"VALTEST-{uuid4().hex[:8].upper()}",
        name="Portfolio Valuation Test Instrument",
        exchange="TEST",
        asset_class="equity",
        currency=currency,
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


@pytest.fixture(autouse=True)
async def clean_portfolio_valuation_test_data(
    db_session,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("portfolio-valuation-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("VALTEST-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_empty_portfolio_has_empty_valuation(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Empty"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/valuation",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "empty"
    assert body["positions"] == []
    assert body["currencies"] == []


@pytest.mark.asyncio
async def test_fresh_quote_produces_market_value_and_unrealized_pnl(
    client: AsyncClient,
    db_session,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    quote_timestamp = datetime.now(UTC)

    db_session.add(
        MarketQuote(
            instrument_id=instrument.id,
            timestamp=quote_timestamp,
            price=Decimal("120"),
            bid=Decimal("119.90"),
            ask=Decimal("120.10"),
            volume=Decimal("1000"),
            source="test-provider",
        ),
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Valued"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "100",
        },
        headers=headers,
    )

    assert position_response.status_code == 200

    response = await client.get(
        f"/portfolios/{portfolio_id}/valuation",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "current"
    assert len(body["positions"]) == 1

    valuation = body["positions"][0]

    assert valuation["quote_quality"]["status"] == "fresh"
    assert Decimal(str(valuation["quote"]["price"])) == Decimal("120")
    assert Decimal(str(valuation["cost_basis"])) == Decimal("1000")
    assert Decimal(str(valuation["market_value"])) == Decimal("1200")
    assert Decimal(str(valuation["unrealized_pnl"])) == Decimal("200")
    assert Decimal(str(valuation["unrealized_pnl_percent"])) == Decimal("0.2")

    currencies = body["currencies"]

    assert len(currencies) == 1
    assert currencies[0]["currency"] == "USD"
    assert currencies[0]["quality"] == "current"
    assert Decimal(str(currencies[0]["cost_basis"])) == Decimal("1000")
    assert Decimal(str(currencies[0]["market_value"])) == Decimal("1200")
    assert Decimal(str(currencies[0]["unrealized_pnl"])) == Decimal("200")


@pytest.mark.asyncio
async def test_stale_quote_does_not_produce_current_market_value(
    client: AsyncClient,
    db_session,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    stale_timestamp = datetime.now(UTC) - timedelta(days=1)

    db_session.add(
        MarketQuote(
            instrument_id=instrument.id,
            timestamp=stale_timestamp,
            price=Decimal("120"),
            source="test-provider",
        ),
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Stale"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "100",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/valuation",
        params={
            "maximum_age_seconds": 900,
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "stale"

    valuation = body["positions"][0]

    assert valuation["quote_quality"]["status"] == "stale"
    assert valuation["quote"] is None
    assert Decimal(str(valuation["cost_basis"])) == Decimal("1000")
    assert valuation["market_value"] is None
    assert valuation["unrealized_pnl"] is None
    assert valuation["unrealized_pnl_percent"] is None

    assert body["currencies"][0]["quality"] == "stale"
    assert body["currencies"][0]["market_value"] is None
    assert body["currencies"][0]["unrealized_pnl"] is None


@pytest.mark.asyncio
async def test_missing_quote_returns_unavailable_quality(
    client: AsyncClient,
    db_session,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Unavailable"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "100",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/valuation",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "unavailable"

    valuation = body["positions"][0]

    assert valuation["quote_quality"]["status"] == "unavailable"
    assert valuation["quote"] is None
    assert Decimal(str(valuation["cost_basis"])) == Decimal("1000")
    assert valuation["market_value"] is None
    assert valuation["unrealized_pnl"] is None


@pytest.mark.asyncio
async def test_multiple_currencies_are_not_combined(
    client: AsyncClient,
    db_session,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    usd_instrument = await create_test_instrument(
        db_session,
        currency="USD",
    )
    eur_instrument = await create_test_instrument(
        db_session,
        currency="EUR",
    )

    quote_timestamp = datetime.now(UTC)

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=usd_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("120"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=eur_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("50"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Multi Currency"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{usd_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "100",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{eur_instrument.id}",
        json={
            "quantity": "4",
            "average_cost": "40",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/valuation",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "current"
    assert {item["currency"] for item in body["currencies"]} == {
        "USD",
        "EUR",
    }

    by_currency = {item["currency"]: item for item in body["currencies"]}

    assert Decimal(str(by_currency["USD"]["market_value"])) == Decimal("1200")
    assert Decimal(str(by_currency["EUR"]["market_value"])) == Decimal("200")

    assert Decimal(str(by_currency["USD"]["unrealized_pnl"])) == Decimal("200")
    assert Decimal(str(by_currency["EUR"]["unrealized_pnl"])) == Decimal("40")


@pytest.mark.asyncio
async def test_portfolio_valuation_respects_ownership(
    client: AsyncClient,
    db_session,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    await create_test_instrument(db_session)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Private Valuation"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/valuation",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_valuation_maximum_quote_age_is_validated(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Validation"},
        headers={"Authorization": f"Bearer {token}"},
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/valuation",
        params={"maximum_age_seconds": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

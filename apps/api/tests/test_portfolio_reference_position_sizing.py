from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.instrument import Instrument
from app.db.models.market_data import MarketQuote
from app.db.models.user import User


async def create_authenticated_user(
    client: AsyncClient,
) -> tuple[str, str]:
    email = f"portfolio-sizing-{uuid4().hex}@example.com"
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
    currency: str = "USD",
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=f"SIZETEST-{uuid4().hex[:8].upper()}",
        name="Portfolio Reference Sizing Test Instrument",
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
async def clean_portfolio_reference_position_sizing_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("portfolio-sizing-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("SIZETEST-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_reference_position_sizing_requires_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/portfolios/{uuid4()}/reference-position-sizing",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_portfolio_returns_empty_reference_sizing(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Empty Reference Sizing"},
        headers=headers,
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/reference-position-sizing",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "empty"
    assert body["positions"] == []
    assert body["currencies"] == []


@pytest.mark.asyncio
async def test_current_currency_positions_receive_equal_reference_sizing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    first_instrument = await create_test_instrument(db_session)
    second_instrument = await create_test_instrument(db_session)

    quote_timestamp = datetime.now(UTC)

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=first_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("120"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=second_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("50"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Reference Sizing"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{first_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "100",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{second_instrument.id}",
        json={
            "quantity": "4",
            "average_cost": "40",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/reference-position-sizing",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"
    assert len(body["positions"]) == 2
    assert len(body["currencies"]) == 1

    positions = {item["position"]["symbol"]: item for item in body["positions"]}

    first = positions[first_instrument.symbol]
    second = positions[second_instrument.symbol]

    expected_weight = Decimal("0.5")
    expected_reference_value = Decimal("700")

    assert Decimal(str(first["current_market_value"])) == Decimal("1200")
    assert Decimal(str(second["current_market_value"])) == Decimal("200")

    assert Decimal(str(first["current_weight"])) == Decimal("1200") / Decimal("1400")
    assert Decimal(str(second["current_weight"])) == Decimal("200") / Decimal("1400")

    assert Decimal(str(first["reference_weight"])) == expected_weight
    assert Decimal(str(second["reference_weight"])) == expected_weight

    assert Decimal(str(first["reference_market_value"])) == expected_reference_value
    assert Decimal(str(second["reference_market_value"])) == expected_reference_value

    assert Decimal(str(first["reference_quantity"])) == (
        expected_reference_value / Decimal("120")
    )
    assert Decimal(str(second["reference_quantity"])) == (
        expected_reference_value / Decimal("50")
    )

    currency = body["currencies"][0]

    assert currency["currency"] == "USD"
    assert currency["quality"] == "current"
    assert Decimal(str(currency["current_market_value"])) == Decimal("1400")
    assert Decimal(str(currency["reference_weight"])) == Decimal("0.5")
    assert Decimal(str(currency["reference_market_value"])) == Decimal("700")


@pytest.mark.asyncio
async def test_multiple_currencies_are_sized_independently(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    usd_first = await create_test_instrument(
        db_session,
        currency="USD",
    )
    usd_second = await create_test_instrument(
        db_session,
        currency="USD",
    )
    eur = await create_test_instrument(
        db_session,
        currency="EUR",
    )

    quote_timestamp = datetime.now(UTC)

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=usd_first.id,
                timestamp=quote_timestamp,
                price=Decimal("100"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=usd_second.id,
                timestamp=quote_timestamp,
                price=Decimal("50"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=eur.id,
                timestamp=quote_timestamp,
                price=Decimal("80"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Independent Currencies"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{usd_first.id}",
        json={
            "quantity": "10",
            "average_cost": "90",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{usd_second.id}",
        json={
            "quantity": "4",
            "average_cost": "45",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{eur.id}",
        json={
            "quantity": "5",
            "average_cost": "70",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/reference-position-sizing",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"

    currencies = {item["currency"]: item for item in body["currencies"]}

    assert Decimal(str(currencies["USD"]["current_market_value"])) == Decimal("1200")
    assert Decimal(str(currencies["USD"]["reference_market_value"])) == Decimal("600")
    assert Decimal(str(currencies["EUR"]["current_market_value"])) == Decimal("400")
    assert Decimal(str(currencies["EUR"]["reference_market_value"])) == Decimal("400")


@pytest.mark.asyncio
async def test_stale_position_blocks_reference_sizing_for_its_currency(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    fresh_instrument = await create_test_instrument(db_session)
    stale_instrument = await create_test_instrument(db_session)

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=fresh_instrument.id,
                timestamp=datetime.now(UTC),
                price=Decimal("100"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=stale_instrument.id,
                timestamp=datetime.now(UTC) - timedelta(days=1),
                price=Decimal("50"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Stale Reference Sizing"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{fresh_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "90",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{stale_instrument.id}",
        json={
            "quantity": "4",
            "average_cost": "40",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/reference-position-sizing",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "none"

    for position in body["positions"]:
        assert position["quality"] == "unavailable"
        assert position["reference_market_value"] is None
        assert position["reference_quantity"] is None
        assert position["quantity_delta"] is None

    assert body["currencies"][0]["quality"] == "unavailable"
    assert body["currencies"][0]["current_market_value"] is None


@pytest.mark.asyncio
async def test_mixed_currency_quality_returns_partial_reference_sizing(
    client: AsyncClient,
    db_session: AsyncSession,
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

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=usd_instrument.id,
                timestamp=datetime.now(UTC),
                price=Decimal("100"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=eur_instrument.id,
                timestamp=datetime.now(UTC) - timedelta(days=1),
                price=Decimal("80"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Partial Reference Sizing"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{usd_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "90",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{eur_instrument.id}",
        json={
            "quantity": "5",
            "average_cost": "70",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/reference-position-sizing",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "partial"

    currencies = {item["currency"]: item for item in body["currencies"]}

    assert currencies["USD"]["quality"] == "current"
    assert currencies["EUR"]["quality"] == "unavailable"

    positions = {item["position"]["symbol"]: item for item in body["positions"]}

    usd_position = positions[usd_instrument.symbol]
    eur_position = positions[eur_instrument.symbol]

    assert usd_position["quality"] == "current"
    assert usd_position["reference_market_value"] is not None
    assert usd_position["reference_quantity"] is not None

    assert eur_position["quality"] == "unavailable"
    assert eur_position["reference_market_value"] is None
    assert eur_position["reference_quantity"] is None


@pytest.mark.asyncio
async def test_reference_position_sizing_respects_ownership(
    client: AsyncClient,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Private Reference Sizing"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/reference-position-sizing",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reference_position_sizing_maximum_quote_age_is_validated(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Reference Sizing Validation"},
        headers={"Authorization": f"Bearer {token}"},
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/reference-position-sizing",
        params={"maximum_age_seconds": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

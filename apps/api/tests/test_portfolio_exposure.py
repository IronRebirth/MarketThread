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
    email = f"portfolio-exposure-{uuid4().hex}@example.com"
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
    currency: str = "USD",
    asset_class: str = "equity",
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=f"EXPOSURE-{uuid4().hex[:8].upper()}",
        name="Portfolio Exposure Test Instrument",
        exchange="TEST",
        asset_class=asset_class,
        currency=currency,
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


@pytest.fixture(autouse=True)
async def clean_portfolio_exposure_test_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("portfolio-exposure-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("EXPOSURE-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_portfolio_exposure_requires_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/portfolios/{uuid4()}/exposure",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_portfolio_has_empty_exposure(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Empty Exposure"},
        headers=headers,
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/exposure",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "empty"
    assert body["currencies"] == []
    assert body["asset_classes"] == []
    assert body["positions"] == []


@pytest.mark.asyncio
async def test_current_exposure_calculates_position_and_asset_class_weights(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    first_instrument = await create_test_instrument(
        db_session,
        asset_class="equity",
    )
    second_instrument = await create_test_instrument(
        db_session,
        asset_class="etf",
    )

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
        json={"name": "Current Exposure"},
        headers=headers,
    )

    assert create_response.status_code == 201
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
        f"/portfolios/{portfolio_id}/exposure",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "current"
    assert len(body["positions"]) == 2
    assert len(body["asset_classes"]) == 2

    positions_by_symbol = {
        item["position"]["symbol"]: item for item in body["positions"]
    }

    first_position = positions_by_symbol[first_instrument.symbol]
    second_position = positions_by_symbol[second_instrument.symbol]

    assert Decimal(str(first_position["market_value"])) == Decimal("1200")
    assert Decimal(str(second_position["market_value"])) == Decimal("200")

    assert Decimal(str(first_position["market_value_weight"])) == Decimal(
        "1200"
    ) / Decimal("1400")
    assert Decimal(str(second_position["market_value_weight"])) == Decimal(
        "200"
    ) / Decimal("1400")

    asset_classes = {item["asset_class"]: item for item in body["asset_classes"]}

    assert Decimal(
        str(asset_classes["equity"]["market_value"]),
    ) == Decimal("1200")
    assert Decimal(
        str(asset_classes["etf"]["market_value"]),
    ) == Decimal("200")
    assert Decimal(str(asset_classes["equity"]["market_value_weight"])) == Decimal(
        "1200"
    ) / Decimal("1400")
    assert Decimal(str(asset_classes["etf"]["market_value_weight"])) == Decimal(
        "200"
    ) / Decimal("1400")


@pytest.mark.asyncio
async def test_stale_quote_does_not_produce_exposure_weights(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    db_session.add(
        MarketQuote(
            instrument_id=instrument.id,
            timestamp=datetime.now(UTC) - timedelta(days=1),
            price=Decimal("120"),
            source="test-provider",
        ),
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Stale Exposure"},
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
        f"/portfolios/{portfolio_id}/exposure",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "stale"

    position = body["positions"][0]

    assert position["quality"] == "stale"
    assert position["market_value"] is None
    assert position["market_value_weight"] is None

    asset_class = body["asset_classes"][0]

    assert asset_class["quality"] == "stale"
    assert asset_class["market_value"] is None
    assert asset_class["market_value_weight"] is None


@pytest.mark.asyncio
async def test_mixed_quote_quality_does_not_create_partial_currency_weights(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    fresh_instrument = await create_test_instrument(
        db_session,
        asset_class="equity",
    )
    stale_instrument = await create_test_instrument(
        db_session,
        asset_class="etf",
    )

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=fresh_instrument.id,
                timestamp=datetime.now(UTC),
                price=Decimal("120"),
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
        json={"name": "Mixed Exposure"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{fresh_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "100",
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
        f"/portfolios/{portfolio_id}/exposure",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "stale"

    for position in body["positions"]:
        assert position["market_value_weight"] is None

    for asset_class in body["asset_classes"]:
        assert asset_class["market_value_weight"] is None


@pytest.mark.asyncio
async def test_multiple_currencies_remain_separate(
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
        json={"name": "Multi Currency Exposure"},
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
        f"/portfolios/{portfolio_id}/exposure",
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

    assert Decimal(
        str(by_currency["USD"]["market_value"]),
    ) == Decimal("1200")
    assert Decimal(
        str(by_currency["EUR"]["market_value"]),
    ) == Decimal("200")


@pytest.mark.asyncio
async def test_portfolio_exposure_respects_ownership(
    client: AsyncClient,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Private Exposure"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/exposure",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_exposure_maximum_quote_age_is_validated(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Exposure Validation"},
        headers={"Authorization": f"Bearer {token}"},
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/exposure",
        params={"maximum_age_seconds": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

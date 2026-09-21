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
    email = f"portfolio-ranges-{uuid4().hex}@example.com"
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
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=f"RANGETEST-{uuid4().hex[:8].upper()}",
        name="Portfolio Allocation Range Test Instrument",
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
async def clean_portfolio_allocation_range_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("portfolio-ranges-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("RANGETEST-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_allocation_ranges_require_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/portfolios/{uuid4()}/allocation-ranges",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_portfolio_returns_empty_allocation_ranges(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Empty Allocation Ranges"},
        headers=headers,
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/allocation-ranges",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "empty"
    assert body["positions"] == []
    assert body["currencies"] == []


@pytest.mark.asyncio
async def test_current_positions_receive_reference_allocation_ranges(
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
        json={"name": "Allocation Ranges"},
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
        f"/portfolios/{portfolio_id}/allocation-ranges",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"
    assert Decimal(str(body["range_tolerance"])) == Decimal("0.25")
    assert len(body["positions"]) == 2

    positions = {item["position"]["symbol"]: item for item in body["positions"]}

    first = positions[first_instrument.symbol]
    second = positions[second_instrument.symbol]

    assert Decimal(str(first["target_weight"])) == Decimal("0.5")
    assert Decimal(str(second["target_weight"])) == Decimal("0.5")

    assert Decimal(str(first["minimum_weight"])) == Decimal("0.375")
    assert Decimal(str(first["maximum_weight"])) == Decimal("0.625")

    assert Decimal(str(second["minimum_weight"])) == Decimal("0.375")
    assert Decimal(str(second["maximum_weight"])) == Decimal("0.625")

    assert Decimal(str(first["current_weight"])) == Decimal("1200") / Decimal("1400")
    assert Decimal(str(second["current_weight"])) == Decimal("200") / Decimal("1400")

    assert first["within_range"] is False
    assert second["within_range"] is False

    currency = body["currencies"][0]

    assert currency["currency"] == "USD"
    assert currency["quality"] == "current"
    assert Decimal(str(currency["current_market_value"])) == Decimal("1400")

    assert Decimal(str(currency["minimum_market_value"])) == Decimal("525")
    assert Decimal(str(currency["target_market_value"])) == Decimal("700")
    assert Decimal(str(currency["maximum_market_value"])) == Decimal("875")


@pytest.mark.asyncio
async def test_custom_range_tolerance_is_applied(
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
                price=Decimal("100"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=second_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("100"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Custom Range"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{first_instrument.id}",
        json={
            "quantity": "5",
            "average_cost": "100",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{second_instrument.id}",
        json={
            "quantity": "5",
            "average_cost": "100",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/allocation-ranges",
        params={"range_tolerance": "0.5"},
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert Decimal(str(body["range_tolerance"])) == Decimal("0.5")

    for position in body["positions"]:
        assert Decimal(str(position["minimum_weight"])) == Decimal("0.25")
        assert Decimal(str(position["target_weight"])) == Decimal("0.5")
        assert Decimal(str(position["maximum_weight"])) == Decimal("0.75")
        assert position["within_range"] is True


@pytest.mark.asyncio
async def test_multiple_currencies_remain_separate(
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
                price=Decimal("100"),
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
        json={"name": "Separate Currencies"},
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
            "quantity": "2",
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
        f"/portfolios/{portfolio_id}/allocation-ranges",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"

    currencies = {item["currency"]: item for item in body["currencies"]}

    assert Decimal(str(currencies["USD"]["target_weight"])) == Decimal("0.5")
    assert Decimal(str(currencies["EUR"]["target_weight"])) == Decimal("1")

    assert Decimal(str(currencies["USD"]["target_market_value"])) == Decimal("600")
    assert Decimal(str(currencies["EUR"]["target_market_value"])) == Decimal("400")


@pytest.mark.asyncio
async def test_stale_currency_is_unavailable_but_keeps_reference_weights(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    fresh_instrument = await create_test_instrument(
        db_session,
        currency="USD",
    )
    stale_instrument = await create_test_instrument(
        db_session,
        currency="USD",
    )

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
        json={"name": "Unavailable Currency"},
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
        f"/portfolios/{portfolio_id}/allocation-ranges",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "none"

    assert len(body["positions"]) == 2

    for position in body["positions"]:
        assert position["quality"] == "unavailable"
        assert position["current_market_value"] is None
        assert position["current_weight"] is None
        assert position["minimum_market_value"] is None
        assert position["target_market_value"] is None
        assert position["maximum_market_value"] is None
        assert position["within_range"] is None
        assert Decimal(str(position["target_weight"])) == Decimal("0.5")

    assert body["currencies"][0]["quality"] == "unavailable"
    assert body["currencies"][0]["current_market_value"] is None


@pytest.mark.asyncio
async def test_mixed_currency_quality_returns_partial_ranges(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    usd = await create_test_instrument(
        db_session,
        currency="USD",
    )
    eur = await create_test_instrument(
        db_session,
        currency="EUR",
    )

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=usd.id,
                timestamp=datetime.now(UTC),
                price=Decimal("100"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=eur.id,
                timestamp=datetime.now(UTC) - timedelta(days=1),
                price=Decimal("80"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Partial Ranges"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{usd.id}",
        json={
            "quantity": "10",
            "average_cost": "90",
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
        f"/portfolios/{portfolio_id}/allocation-ranges",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "partial"

    currencies = {item["currency"]: item for item in body["currencies"]}

    assert currencies["USD"]["quality"] == "current"
    assert currencies["EUR"]["quality"] == "unavailable"


@pytest.mark.asyncio
async def test_allocation_range_ownership_is_enforced(
    client: AsyncClient,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Private Allocation Ranges"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/allocation-ranges",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_allocation_range_query_parameters_are_validated(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Allocation Range Validation"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    zero_tolerance = await client.get(
        f"/portfolios/{portfolio_id}/allocation-ranges",
        params={"range_tolerance": "0"},
        headers=headers,
    )

    assert zero_tolerance.status_code == 422

    excessive_tolerance = await client.get(
        f"/portfolios/{portfolio_id}/allocation-ranges",
        params={"range_tolerance": "1.1"},
        headers=headers,
    )

    assert excessive_tolerance.status_code == 422

    invalid_quote_age = await client.get(
        f"/portfolios/{portfolio_id}/allocation-ranges",
        params={"maximum_age_seconds": "0"},
        headers=headers,
    )

    assert invalid_quote_age.status_code == 422

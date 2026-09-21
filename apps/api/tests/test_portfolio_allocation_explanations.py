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
    email = f"portfolio-explanations-{uuid4().hex}@example.com"
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
        symbol=f"EXPLTEST-{uuid4().hex[:8].upper()}",
        name="Portfolio Allocation Explanation Test Instrument",
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
async def clean_portfolio_allocation_explanation_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("portfolio-explanations-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("EXPLTEST-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_allocation_explanations_require_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/portfolios/{uuid4()}/allocation-explanations",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_portfolio_returns_empty_explanations(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Empty Allocation Explanations"},
        headers=headers,
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/allocation-explanations",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "empty"
    assert body["explanation_count"] == 0
    assert body["outside_range_count"] == 0
    assert body["violation_count"] == 0
    assert body["items"] == []
    assert body["currencies"] == []


@pytest.mark.asyncio
async def test_allocation_explanations_describe_range_state(
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
        json={"name": "Allocation Explanations"},
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
        f"/portfolios/{portfolio_id}/allocation-explanations",
        params={
            "maximum_position_weight": "1.0",
            "maximum_asset_class_weight": "1.0",
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"
    assert body["explanation_count"] == 2
    assert body["outside_range_count"] == 2
    assert body["violation_count"] == 0

    items = {item["position"]["symbol"]: item for item in body["items"]}

    first = items[first_instrument.symbol]
    second = items[second_instrument.symbol]

    assert first["status"] == "above_maximum"
    assert second["status"] == "below_minimum"

    assert Decimal(str(first["current_weight"])) == Decimal("1200") / Decimal("1400")
    assert Decimal(str(second["current_weight"])) == Decimal("200") / Decimal("1400")

    assert Decimal(str(first["minimum_weight"])) == Decimal("0.375")
    assert Decimal(str(first["target_weight"])) == Decimal("0.5")
    assert Decimal(str(first["maximum_weight"])) == Decimal("0.625")

    assert "above" in first["explanation"]
    assert "target" in first["explanation"]

    assert "below" in second["explanation"]
    assert "target" in second["explanation"]


@pytest.mark.asyncio
async def test_within_range_position_is_explained_without_violation(
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
        asset_class="equity",
    )

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
        json={"name": "Within Range Explanations"},
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
        f"/portfolios/{portfolio_id}/allocation-explanations",
        params={
            "maximum_position_weight": "1.0",
            "maximum_asset_class_weight": "1.0",
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["outside_range_count"] == 0
    assert body["violation_count"] == 0

    for item in body["items"]:
        assert item["status"] == "within_range"
        assert item["constraint_violation_count"] == 0
        assert item["violated_constraints"] == []
        assert "within" in item["explanation"]


@pytest.mark.asyncio
async def test_constraint_violations_are_included_in_explanations(
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
        asset_class="equity",
    )
    third_instrument = await create_test_instrument(
        db_session,
        asset_class="etf",
    )

    quote_timestamp = datetime.now(UTC)

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=first_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("80"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=second_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("10"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=third_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("10"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Constraint Explanations"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{first_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "70",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{second_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "8",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{third_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "8",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/allocation-explanations",
        params={
            "maximum_position_weight": "0.50",
            "maximum_asset_class_weight": "0.75",
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["violation_count"] == 2

    violations = {
        item["position"]["symbol"]: item
        for item in body["items"]
        if item["constraint_violation_count"] > 0
    }

    first = violations[first_instrument.symbol]

    assert first["constraint_violation_count"] == 2
    assert set(first["violated_constraints"]) == {
        "maximum_position_weight",
        "maximum_asset_class_weight",
    }

    assert "maximum_position_weight" in first["explanation"]
    assert "maximum_asset_class_weight" in first["explanation"]


@pytest.mark.asyncio
async def test_multiple_currencies_are_explained_independently(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    usd_first = await create_test_instrument(
        db_session,
        currency="USD",
        asset_class="equity",
    )
    usd_second = await create_test_instrument(
        db_session,
        currency="USD",
        asset_class="etf",
    )
    eur = await create_test_instrument(
        db_session,
        currency="EUR",
        asset_class="equity",
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
        json={"name": "Independent Currency Explanations"},
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
            "quantity": "10",
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
        f"/portfolios/{portfolio_id}/allocation-explanations",
        params={
            "maximum_position_weight": "1.0",
            "maximum_asset_class_weight": "1.0",
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"

    currencies = {item["currency"]: item for item in body["currencies"]}

    assert currencies["USD"]["position_count"] == 2
    assert currencies["USD"]["outside_range_count"] == 0
    assert currencies["EUR"]["position_count"] == 1
    assert currencies["EUR"]["outside_range_count"] == 0


@pytest.mark.asyncio
async def test_stale_currency_is_explained_as_unavailable(
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
        json={"name": "Unavailable Explanations"},
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
        f"/portfolios/{portfolio_id}/allocation-explanations",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "none"

    assert all(item["quality"] == "unavailable" for item in body["items"])

    assert all(item["status"] == "unavailable" for item in body["items"])

    assert body["currencies"][0]["quality"] == "unavailable"


@pytest.mark.asyncio
async def test_allocation_explanations_respect_ownership(
    client: AsyncClient,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Private Allocation Explanations"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/allocation-explanations",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_allocation_explanation_parameters_are_validated(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Allocation Explanation Validation"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    invalid_range = await client.get(
        f"/portfolios/{portfolio_id}/allocation-explanations",
        params={"range_tolerance": "0"},
        headers=headers,
    )

    assert invalid_range.status_code == 422

    invalid_position_limit = await client.get(
        f"/portfolios/{portfolio_id}/allocation-explanations",
        params={"maximum_position_weight": "1.1"},
        headers=headers,
    )

    assert invalid_position_limit.status_code == 422

    invalid_asset_class_limit = await client.get(
        f"/portfolios/{portfolio_id}/allocation-explanations",
        params={"maximum_asset_class_weight": "0"},
        headers=headers,
    )

    assert invalid_asset_class_limit.status_code == 422

    invalid_quote_age = await client.get(
        f"/portfolios/{portfolio_id}/allocation-explanations",
        params={"maximum_age_seconds": "0"},
        headers=headers,
    )

    assert invalid_quote_age.status_code == 422

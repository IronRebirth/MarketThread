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
    email = f"portfolio-risk-constraints-{uuid4().hex}@example.com"
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
    asset_class: str = "equity",
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=f"RISKTEST-{uuid4().hex[:8].upper()}",
        name="Portfolio Risk Constraint Test Instrument",
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
async def clean_portfolio_risk_constraint_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("portfolio-risk-constraints-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("RISKTEST-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_risk_constraints_require_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/portfolios/{uuid4()}/risk-constraints",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_portfolio_returns_empty_constraints(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Empty Risk Constraints"},
        headers=headers,
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-constraints",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "empty"
    assert body["evaluated_constraint_count"] == 0
    assert body["violation_count"] == 0
    assert body["constraints"] == []
    assert body["currencies"] == []


@pytest.mark.asyncio
async def test_current_portfolio_constraints_pass(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    equity_instrument = await create_test_instrument(
        db_session,
        asset_class="equity",
    )
    etf_instrument = await create_test_instrument(
        db_session,
        asset_class="etf",
    )

    quote_timestamp = datetime.now(UTC)

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=equity_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("60"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=etf_instrument.id,
                timestamp=quote_timestamp,
                price=Decimal("40"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Passing Risk Constraints"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{equity_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "50",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{etf_instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "35",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-constraints",
        params={
            "maximum_position_weight": "0.70",
            "maximum_asset_class_weight": "0.70",
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"
    assert body["evaluated_constraint_count"] == 4
    assert body["violation_count"] == 0

    statuses = {constraint["status"] for constraint in body["constraints"]}

    assert statuses == {"pass"}

    assert Decimal(str(body["maximum_position_weight"])) == Decimal("0.70")
    assert Decimal(str(body["maximum_asset_class_weight"])) == Decimal("0.70")

    currency = body["currencies"][0]

    assert currency["currency"] == "USD"
    assert currency["quality"] == "current"
    assert Decimal(str(currency["current_market_value"])) == Decimal("1000")
    assert currency["violation_count"] == 0


@pytest.mark.asyncio
async def test_position_and_asset_class_violations_are_reported(
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
        json={"name": "Violating Risk Constraints"},
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
        f"/portfolios/{portfolio_id}/risk-constraints",
        params={
            "maximum_position_weight": "0.50",
            "maximum_asset_class_weight": "0.75",
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"
    assert body["violation_count"] == 2

    violations = [
        constraint
        for constraint in body["constraints"]
        if constraint["status"] == "violation"
    ]

    assert len(violations) == 2

    violation_kinds = {constraint["kind"] for constraint in violations}

    assert violation_kinds == {
        "maximum_position_weight",
        "maximum_asset_class_weight",
    }

    position_violation = next(
        constraint
        for constraint in violations
        if constraint["kind"] == "maximum_position_weight"
    )

    assert position_violation["subject"] == first_instrument.symbol
    assert Decimal(str(position_violation["observed_weight"])) == (
        Decimal("800") / Decimal("1000")
    )
    assert Decimal(str(position_violation["limit"])) == Decimal("0.50")

    asset_class_violation = next(
        constraint
        for constraint in violations
        if constraint["kind"] == "maximum_asset_class_weight"
    )

    assert asset_class_violation["subject"] == "equity"
    assert Decimal(str(asset_class_violation["observed_weight"])) == (
        Decimal("900") / Decimal("1000")
    )
    assert Decimal(str(asset_class_violation["limit"])) == Decimal("0.75")


@pytest.mark.asyncio
async def test_multiple_currencies_are_evaluated_independently(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    usd = await create_test_instrument(
        db_session,
        currency="USD",
        asset_class="equity",
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
                instrument_id=usd.id,
                timestamp=quote_timestamp,
                price=Decimal("100"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=eur.id,
                timestamp=quote_timestamp,
                price=Decimal("200"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Independent Risk Constraints"},
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
            "quantity": "2",
            "average_cost": "180",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-constraints",
        params={
            "maximum_position_weight": "1.0",
            "maximum_asset_class_weight": "1.0",
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "sufficient"
    assert body["violation_count"] == 0

    currencies = {item["currency"]: item for item in body["currencies"]}

    assert Decimal(
        str(currencies["USD"]["current_market_value"]),
    ) == Decimal("1000")

    assert Decimal(
        str(currencies["EUR"]["current_market_value"]),
    ) == Decimal("400")

    assert all(constraint["status"] == "pass" for constraint in body["constraints"])


@pytest.mark.asyncio
async def test_stale_currency_is_unavailable(
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
        json={"name": "Unavailable Risk Constraints"},
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
        f"/portfolios/{portfolio_id}/risk-constraints",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "none"
    assert body["evaluated_constraint_count"] == 0
    assert body["violation_count"] == 0

    assert all(
        constraint["status"] == "unavailable" for constraint in body["constraints"]
    )

    assert body["currencies"][0]["quality"] == "unavailable"


@pytest.mark.asyncio
async def test_mixed_currency_quality_returns_partial_constraints(
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
        json={"name": "Partial Risk Constraints"},
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
        f"/portfolios/{portfolio_id}/risk-constraints",
        params={
            "maximum_position_weight": "1.0",
            "maximum_asset_class_weight": "1.0",
        },
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "partial"
    assert body["evaluated_constraint_count"] == 2
    assert body["violation_count"] == 0

    by_currency = {item["currency"]: item for item in body["currencies"]}

    assert by_currency["USD"]["quality"] == "current"
    assert by_currency["EUR"]["quality"] == "unavailable"


@pytest.mark.asyncio
async def test_risk_constraints_respect_ownership(
    client: AsyncClient,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Private Risk Constraints"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-constraints",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_risk_constraint_parameters_are_validated(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Risk Constraint Validation"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    zero_position_limit = await client.get(
        f"/portfolios/{portfolio_id}/risk-constraints",
        params={"maximum_position_weight": "0"},
        headers=headers,
    )

    assert zero_position_limit.status_code == 422

    excessive_asset_class_limit = await client.get(
        f"/portfolios/{portfolio_id}/risk-constraints",
        params={"maximum_asset_class_weight": "1.1"},
        headers=headers,
    )

    assert excessive_asset_class_limit.status_code == 422

    invalid_quote_age = await client.get(
        f"/portfolios/{portfolio_id}/risk-constraints",
        params={"maximum_age_seconds": "0"},
        headers=headers,
    )

    assert invalid_quote_age.status_code == 422

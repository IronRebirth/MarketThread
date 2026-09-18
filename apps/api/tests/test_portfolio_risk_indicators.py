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
    email = f"portfolio-risk-indicator-{uuid4().hex}@example.com"
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
        symbol=f"RISKIND-{uuid4().hex[:8].upper()}",
        name="Portfolio Risk Indicator Test Instrument",
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
async def clean_portfolio_risk_indicator_test_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("portfolio-risk-indicator-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("RISKIND-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_risk_indicators_require_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f"/portfolios/{uuid4()}/risk-indicators",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_portfolio_has_no_risk_indicators(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Empty Risk Indicators"},
        headers=headers,
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-indicators",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "empty"
    assert body["indicators"] == []


@pytest.mark.asyncio
async def test_single_position_currency_exposure_creates_structural_indicator(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    db_session.add(
        MarketQuote(
            instrument_id=instrument.id,
            timestamp=datetime.now(UTC),
            price=Decimal("120"),
            source="test-provider",
        ),
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Single Position Risk"},
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
        f"/portfolios/{portfolio_id}/risk-indicators",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "current"
    assert len(body["indicators"]) == 1

    indicator = body["indicators"][0]

    assert indicator["kind"] == "single_instrument_currency_exposure"
    assert indicator["level"] == "attention"
    assert indicator["currency"] == "USD"
    assert indicator["position_count"] == 1
    assert indicator["asset_class"] is None


@pytest.mark.asyncio
async def test_single_asset_class_indicator_requires_multiple_positions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = await create_test_instrument(
        db_session,
        asset_class="equity",
    )
    second = await create_test_instrument(
        db_session,
        asset_class="equity",
    )

    timestamp = datetime.now(UTC)

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=first.id,
                timestamp=timestamp,
                price=Decimal("100"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=second.id,
                timestamp=timestamp,
                price=Decimal("80"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Single Asset Class"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{first.id}",
        json={
            "quantity": "5",
            "average_cost": "90",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{second.id}",
        json={
            "quantity": "4",
            "average_cost": "70",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-indicators",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "current"

    kinds = {indicator["kind"] for indicator in body["indicators"]}

    assert "single_asset_class_currency_exposure" in kinds
    assert "single_instrument_currency_exposure" not in kinds


@pytest.mark.asyncio
async def test_mixed_asset_classes_do_not_create_single_asset_class_indicator(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    equity = await create_test_instrument(
        db_session,
        asset_class="equity",
    )
    etf = await create_test_instrument(
        db_session,
        asset_class="etf",
    )

    timestamp = datetime.now(UTC)

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=equity.id,
                timestamp=timestamp,
                price=Decimal("100"),
                source="test-provider",
            ),
            MarketQuote(
                instrument_id=etf.id,
                timestamp=timestamp,
                price=Decimal("100"),
                source="test-provider",
            ),
        ],
    )
    await db_session.commit()

    create_response = await client.post(
        "/portfolios",
        json={"name": "Mixed Asset Classes"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    await client.put(
        f"/portfolios/{portfolio_id}/positions/{equity.id}",
        json={
            "quantity": "5",
            "average_cost": "90",
        },
        headers=headers,
    )
    await client.put(
        f"/portfolios/{portfolio_id}/positions/{etf.id}",
        json={
            "quantity": "5",
            "average_cost": "90",
        },
        headers=headers,
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-indicators",
        headers=headers,
    )

    assert response.status_code == 200

    kinds = {indicator["kind"] for indicator in response.json()["indicators"]}

    assert "single_asset_class_currency_exposure" not in kinds
    assert "single_instrument_currency_exposure" not in kinds


@pytest.mark.asyncio
async def test_stale_valuation_creates_data_quality_indicator(
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
        json={"name": "Stale Risk Indicators"},
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
        f"/portfolios/{portfolio_id}/risk-indicators",
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["quality"] == "stale"

    quality_indicators = [
        indicator
        for indicator in body["indicators"]
        if indicator["kind"] == "valuation_data_quality"
    ]

    assert len(quality_indicators) == 1
    assert quality_indicators[0]["level"] == "attention"


@pytest.mark.asyncio
async def test_risk_indicators_respect_ownership(
    client: AsyncClient,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Private Risk Indicators"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-indicators",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_risk_indicator_maximum_quote_age_is_validated(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Risk Indicator Validation"},
        headers={"Authorization": f"Bearer {token}"},
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-indicators",
        params={"maximum_age_seconds": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

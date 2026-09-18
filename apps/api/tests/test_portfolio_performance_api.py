from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.security import hash_password
from app.db.models.instrument import Instrument
from app.db.models.market_bar import MarketBar
from app.db.models.portfolio import PortfolioPositionRecord, PortfolioRecord
from app.db.models.user import User

TEST_PASSWORD = "StrongPassword123"


async def create_authenticated_user(
    client: AsyncClient,
) -> tuple[User, str]:
    email = f"performance-{uuid4().hex}@example.com"

    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 201

    login_response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    return User(
        email=email,
        password_hash=hash_password(TEST_PASSWORD),
    ), token


async def create_instrument(
    db_session,
    *,
    currency: str = "USD",
) -> Instrument:
    instrument = Instrument(
        symbol=f"PERF{uuid4().hex[:8].upper()}",
        name="Performance Test Instrument",
        exchange="TEST",
        asset_class="equity",
        currency=currency,
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
    response = await client.post(
        "/portfolios",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201

    return response.json()["portfolio_id"]


async def create_bar(
    db_session,
    *,
    instrument_id,
    timestamp: datetime,
    close: str,
) -> None:
    db_session.add(
        MarketBar(
            instrument_id=instrument_id,
            timestamp=timestamp,
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=Decimal("1000"),
            source="performance-test",
        ),
    )

    await db_session.commit()


async def cleanup_portfolio_test(
    db_session,
    *,
    portfolio_id,
    instrument_ids,
) -> None:
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
    await db_session.execute(
        delete(MarketBar).where(
            MarketBar.instrument_id.in_(instrument_ids),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.id.in_(instrument_ids),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_performance_endpoint_returns_historical_values_and_return(
    client: AsyncClient,
    db_session,
) -> None:
    _user, token = await create_authenticated_user(client)

    instrument = await create_instrument(db_session)

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Performance {uuid4().hex[:8]}",
    )

    headers = {"Authorization": f"Bearer {token}"}

    position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "2",
            "average_cost": "100",
        },
        headers=headers,
    )

    assert position_response.status_code == 200

    assessed_at = datetime.now(UTC)

    await create_bar(
        db_session,
        instrument_id=instrument.id,
        timestamp=assessed_at - timedelta(days=3),
        close="100",
    )
    await create_bar(
        db_session,
        instrument_id=instrument.id,
        timestamp=assessed_at - timedelta(days=2),
        close="110",
    )
    await create_bar(
        db_session,
        instrument_id=instrument.id,
        timestamp=assessed_at - timedelta(days=1),
        close="120",
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/performance",
        params={"lookback_days": 10},
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["portfolio"]["portfolio_id"] == portfolio_id
    assert body["quality"] == "sufficient"
    assert body["position_count"] == 1
    assert body["lookback_days"] == 10
    assert body["methodology"].startswith(
        "Constant-position historical proxy",
    )

    assert len(body["currencies"]) == 1

    currency = body["currencies"][0]

    assert currency["currency"] == "USD"
    assert currency["position_count"] == 1
    assert currency["quality"] == "sufficient"
    assert currency["observation_count"] == 3
    assert currency["return_count"] == 2
    assert Decimal(currency["initial_value"]) == Decimal("200")
    assert Decimal(currency["latest_value"]) == Decimal("240")
    assert Decimal(currency["period_return"]) == Decimal("0.2")

    assert [Decimal(point["value"]) for point in currency["points"]] == [
        Decimal("200"),
        Decimal("220"),
        Decimal("240"),
    ]

    assert len(currency["points"]) == 3
    assert currency["sources"] == ["performance-test"]

    await cleanup_portfolio_test(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_performance_endpoint_keeps_currencies_separate(
    client: AsyncClient,
    db_session,
) -> None:
    _user, token = await create_authenticated_user(client)

    usd_instrument = await create_instrument(
        db_session,
        currency="USD",
    )
    eur_instrument = await create_instrument(
        db_session,
        currency="EUR",
    )

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Performance Multi {uuid4().hex[:8]}",
    )

    headers = {"Authorization": f"Bearer {token}"}

    usd_position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{usd_instrument.id}",
        json={
            "quantity": "1",
            "average_cost": "100",
        },
        headers=headers,
    )

    eur_position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{eur_instrument.id}",
        json={
            "quantity": "2",
            "average_cost": "50",
        },
        headers=headers,
    )

    assert usd_position_response.status_code == 200
    assert eur_position_response.status_code == 200

    assessed_at = datetime.now(UTC)

    for instrument_id, prices in (
        (
            usd_instrument.id,
            ("100", "120"),
        ),
        (
            eur_instrument.id,
            ("50", "60"),
        ),
    ):
        for offset, price in zip(
            (2, 1),
            prices,
            strict=True,
        ):
            await create_bar(
                db_session,
                instrument_id=instrument_id,
                timestamp=assessed_at - timedelta(days=offset),
                close=price,
            )

    response = await client.get(
        f"/portfolios/{portfolio_id}/performance",
        params={"lookback_days": 10},
        headers=headers,
    )

    assert response.status_code == 200

    currencies = {item["currency"]: item for item in response.json()["currencies"]}

    assert set(currencies) == {"EUR", "USD"}

    assert Decimal(currencies["USD"]["initial_value"]) == Decimal("100")
    assert Decimal(currencies["USD"]["latest_value"]) == Decimal("120")
    assert Decimal(currencies["USD"]["period_return"]) == Decimal("0.2")

    assert Decimal(currencies["EUR"]["initial_value"]) == Decimal("100")
    assert Decimal(currencies["EUR"]["latest_value"]) == Decimal("120")
    assert Decimal(currencies["EUR"]["period_return"]) == Decimal("0.2")

    await cleanup_portfolio_test(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[
            usd_instrument.id,
            eur_instrument.id,
        ],
    )


@pytest.mark.asyncio
async def test_performance_endpoint_reports_insufficient_history(
    client: AsyncClient,
    db_session,
) -> None:
    _user, token = await create_authenticated_user(client)

    instrument = await create_instrument(db_session)

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Performance Short {uuid4().hex[:8]}",
    )

    headers = {"Authorization": f"Bearer {token}"}

    position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "1",
            "average_cost": "100",
        },
        headers=headers,
    )

    assert position_response.status_code == 200

    assessed_at = datetime.now(UTC)

    await create_bar(
        db_session,
        instrument_id=instrument.id,
        timestamp=assessed_at - timedelta(days=1),
        close="100",
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/performance",
        params={"lookback_days": 10},
        headers=headers,
    )

    assert response.status_code == 200

    currency = response.json()["currencies"][0]

    assert currency["quality"] == "insufficient"
    assert currency["observation_count"] == 1
    assert currency["return_count"] == 0
    assert Decimal(currency["initial_value"]) == Decimal("100")
    assert Decimal(currency["latest_value"]) == Decimal("100")
    assert currency["period_return"] is None

    await cleanup_portfolio_test(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_performance_endpoint_reports_unavailable_without_common_history(
    client: AsyncClient,
    db_session,
) -> None:
    _user, token = await create_authenticated_user(client)

    first_instrument = await create_instrument(db_session)
    second_instrument = await create_instrument(db_session)

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Performance Missing {uuid4().hex[:8]}",
    )

    headers = {"Authorization": f"Bearer {token}"}

    first_position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{first_instrument.id}",
        json={
            "quantity": "1",
            "average_cost": "100",
        },
        headers=headers,
    )
    second_position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{second_instrument.id}",
        json={
            "quantity": "1",
            "average_cost": "100",
        },
        headers=headers,
    )

    assert first_position_response.status_code == 200
    assert second_position_response.status_code == 200

    assessed_at = datetime.now(UTC)

    await create_bar(
        db_session,
        instrument_id=first_instrument.id,
        timestamp=assessed_at - timedelta(days=3),
        close="100",
    )
    await create_bar(
        db_session,
        instrument_id=second_instrument.id,
        timestamp=assessed_at - timedelta(days=1),
        close="100",
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/performance",
        params={"lookback_days": 10},
        headers=headers,
    )

    assert response.status_code == 200

    currency = response.json()["currencies"][0]

    assert currency["quality"] == "unavailable"
    assert currency["observation_count"] == 0
    assert currency["return_count"] == 0
    assert currency["initial_value"] is None
    assert currency["latest_value"] is None
    assert currency["period_return"] is None

    await cleanup_portfolio_test(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[
            first_instrument.id,
            second_instrument.id,
        ],
    )


@pytest.mark.asyncio
async def test_performance_endpoint_is_not_accessible_across_users(
    client: AsyncClient,
    db_session,
) -> None:
    _owner, owner_token = await create_authenticated_user(client)
    _other_user, other_token = await create_authenticated_user(client)

    instrument = await create_instrument(db_session)

    portfolio_id = await create_portfolio(
        client,
        owner_token,
        name=f"Performance Owner {uuid4().hex[:8]}",
    )

    response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "1",
            "average_cost": "100",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200

    other_response = await client.get(
        f"/portfolios/{portfolio_id}/performance",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert other_response.status_code == 404

    await cleanup_portfolio_test(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_performance_endpoint_rejects_invalid_lookback(
    client: AsyncClient,
) -> None:
    _user, token = await create_authenticated_user(client)

    response = await client.get(
        f"/portfolios/{uuid4()}/performance",
        params={"lookback_days": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_performance_endpoint_rejects_lookback_above_limit(
    client: AsyncClient,
) -> None:
    _user, token = await create_authenticated_user(client)

    response = await client.get(
        f"/portfolios/{uuid4()}/performance",
        params={"lookback_days": 3651},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

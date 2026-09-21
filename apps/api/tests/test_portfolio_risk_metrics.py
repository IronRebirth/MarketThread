from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.instrument import Instrument
from app.db.models.market_bar import MarketBar
from app.db.models.portfolio import PortfolioPositionRecord, PortfolioRecord
from app.db.models.portfolio_history import PortfolioPositionHistoryRecord
from app.db.models.user import User
from app.portfolio.risk_metrics import (
    calculate_annualized_volatility,
    calculate_maximum_drawdown,
)

TEST_PASSWORD = "StrongPassword123"


def test_calculates_annualized_volatility_from_sample_standard_deviation() -> None:
    result = calculate_annualized_volatility((0.10, -0.10))

    assert result == pytest.approx(
        0.14142135623730953 * (252**0.5),
        rel=1e-9,
    )


def test_calculates_maximum_drawdown_from_peak_to_trough() -> None:
    result = calculate_maximum_drawdown(
        (100.0, 110.0, 99.0, 105.0),
    )

    assert result[0] == pytest.approx(-0.1)
    assert result[1] == 1
    assert result[2] == 2


async def create_authenticated_user(
    client: AsyncClient,
) -> tuple[User, str]:
    email = f"risk-metrics-{uuid4().hex}@example.com"

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

    token = login_response.cookies["marketthread.access"]

    return User(email=email, password_hash=hash_password(TEST_PASSWORD)), token


async def create_instrument(
    db_session,
    *,
    currency: str = "USD",
) -> Instrument:
    instrument = Instrument(
        symbol=f"RISK{uuid4().hex[:8].upper()}",
        name="Risk Metrics Test Instrument",
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
            source="risk-metrics-test",
        ),
    )

    await db_session.commit()


async def backdate_latest_position_history(
    db_session: AsyncSession,
    *,
    portfolio_id,
    instrument_id,
    recorded_at: datetime,
) -> None:
    result = await db_session.execute(
        select(PortfolioPositionHistoryRecord)
        .where(
            PortfolioPositionHistoryRecord.portfolio_id == portfolio_id,
            PortfolioPositionHistoryRecord.instrument_id == instrument_id,
        )
        .order_by(PortfolioPositionHistoryRecord.sequence_id.desc())
        .limit(1),
    )

    history = result.scalar_one()
    history.recorded_at = recorded_at

    await db_session.commit()
    await db_session.refresh(history)


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
async def test_risk_metrics_endpoint_returns_volatility_and_drawdown(
    client: AsyncClient,
    db_session,
) -> None:
    _user, token = await create_authenticated_user(client)

    instrument = await create_instrument(db_session)

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Risk Metrics {uuid4().hex[:8]}",
    )

    position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "1",
            "average_cost": "100",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert position_response.status_code == 200

    assessed_at = datetime.now(UTC)

    await backdate_latest_position_history(
        db_session,
        portfolio_id=portfolio_id,
        instrument_id=instrument.id,
        recorded_at=assessed_at - timedelta(days=4),
    )

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
        close="99",
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-metrics",
        params={"lookback_days": 10},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["portfolio"]["portfolio_id"] == portfolio_id
    assert body["quality"] == "sufficient"
    assert body["position_count"] == 1
    assert body["annualization_factor"] == 252
    assert body["methodology"].startswith(
        "Time-aware historical portfolio risk analysis",
    )

    assert len(body["currencies"]) == 1

    currency = body["currencies"][0]

    assert currency["currency"] == "USD"
    assert currency["position_count"] == 1
    assert currency["quality"] == "sufficient"
    assert currency["observation_count"] == 3
    assert currency["return_count"] == 2
    assert currency["annualized_volatility"] == pytest.approx(
        0.14142135623730953 * (252**0.5),
        rel=1e-6,
    )
    assert currency["maximum_drawdown"] == pytest.approx(-0.1)
    assert currency["drawdown_peak_on"] is not None
    assert currency["drawdown_trough_on"] is not None

    await cleanup_portfolio_test(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_multiple_currencies_remain_separate(
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
        name=f"Risk Multi {uuid4().hex[:8]}",
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

    await backdate_latest_position_history(
        db_session,
        portfolio_id=portfolio_id,
        instrument_id=usd_instrument.id,
        recorded_at=assessed_at - timedelta(days=4),
    )
    await backdate_latest_position_history(
        db_session,
        portfolio_id=portfolio_id,
        instrument_id=eur_instrument.id,
        recorded_at=assessed_at - timedelta(days=4),
    )

    for instrument_id, prices in (
        (
            usd_instrument.id,
            ("100", "105", "95"),
        ),
        (
            eur_instrument.id,
            ("50", "55", "52"),
        ),
    ):
        for offset, price in zip(
            (3, 2, 1),
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
        f"/portfolios/{portfolio_id}/risk-metrics",
        params={"lookback_days": 10},
        headers=headers,
    )

    assert response.status_code == 200

    currencies = {item["currency"]: item for item in response.json()["currencies"]}

    assert set(currencies) == {"EUR", "USD"}

    assert currencies["USD"]["maximum_drawdown"] == pytest.approx(
        95 / 105 - 1,
    )
    assert currencies["EUR"]["maximum_drawdown"] == pytest.approx(
        52 / 55 - 1,
    )

    await cleanup_portfolio_test(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[
            usd_instrument.id,
            eur_instrument.id,
        ],
    )


@pytest.mark.asyncio
async def test_insufficient_history_does_not_create_volatility(
    client: AsyncClient,
    db_session,
) -> None:
    _user, token = await create_authenticated_user(client)

    instrument = await create_instrument(db_session)

    portfolio_id = await create_portfolio(
        client,
        token,
        name=f"Risk Short {uuid4().hex[:8]}",
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

    await backdate_latest_position_history(
        db_session,
        portfolio_id=portfolio_id,
        instrument_id=instrument.id,
        recorded_at=assessed_at - timedelta(days=3),
    )

    await create_bar(
        db_session,
        instrument_id=instrument.id,
        timestamp=assessed_at - timedelta(days=2),
        close="100",
    )
    await create_bar(
        db_session,
        instrument_id=instrument.id,
        timestamp=assessed_at - timedelta(days=1),
        close="110",
    )

    response = await client.get(
        f"/portfolios/{portfolio_id}/risk-metrics",
        params={"lookback_days": 10},
        headers=headers,
    )

    assert response.status_code == 200

    currency = response.json()["currencies"][0]

    assert currency["quality"] == "insufficient"
    assert currency["observation_count"] == 2
    assert currency["return_count"] == 1
    assert currency["annualized_volatility"] is None
    assert currency["maximum_drawdown"] == 0.0

    await cleanup_portfolio_test(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_risk_metrics_are_not_accessible_across_users(
    client: AsyncClient,
    db_session,
) -> None:
    _owner, owner_token = await create_authenticated_user(client)
    _other_user, other_token = await create_authenticated_user(client)

    instrument = await create_instrument(db_session)

    portfolio_id = await create_portfolio(
        client,
        owner_token,
        name=f"Risk Owner {uuid4().hex[:8]}",
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
        f"/portfolios/{portfolio_id}/risk-metrics",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert other_response.status_code == 404

    await cleanup_portfolio_test(
        db_session,
        portfolio_id=portfolio_id,
        instrument_ids=[instrument.id],
    )


@pytest.mark.asyncio
async def test_risk_metrics_reject_invalid_lookback(
    client: AsyncClient,
) -> None:
    _user, token = await create_authenticated_user(client)

    response = await client.get(
        f"/portfolios/{uuid4()}/risk-metrics",
        params={"lookback_days": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

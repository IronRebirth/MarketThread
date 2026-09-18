from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.instrument import Instrument
from app.db.models.portfolio_history import PortfolioPositionHistoryRecord
from app.db.models.user import User


async def create_authenticated_user(
    client: AsyncClient,
) -> str:
    email = f"portfolio-history-test-{uuid4().hex}@example.com"
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

    return login_response.json()["access_token"]


async def create_test_instrument(
    db_session: AsyncSession,
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=f"HISTTEST-{uuid4().hex[:8].upper()}",
        name="Portfolio History Test Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


@pytest.fixture(autouse=True)
async def clean_portfolio_history_test_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("portfolio-history-test-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("HISTTEST-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_position_create_and_update_are_recorded(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/portfolios",
        json={"name": "History"},
        headers=headers,
    )

    assert create_response.status_code == 201
    portfolio_id = create_response.json()["portfolio_id"]

    first_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "100",
        },
        headers=headers,
    )

    second_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "25",
            "average_cost": "110",
        },
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    result = await db_session.execute(
        select(PortfolioPositionHistoryRecord)
        .where(
            PortfolioPositionHistoryRecord.portfolio_id == portfolio_id,
            PortfolioPositionHistoryRecord.instrument_id == instrument.id,
        )
        .order_by(PortfolioPositionHistoryRecord.sequence_id)
    )

    history = list(result.scalars())

    assert len(history) == 2

    assert history[0].event_type == "created"
    assert history[0].quantity == Decimal("10")
    assert history[0].average_cost == Decimal("100")

    assert history[1].event_type == "updated"
    assert history[1].quantity == Decimal("25")
    assert history[1].average_cost == Decimal("110")

    assert history[0].sequence_id < history[1].sequence_id


@pytest.mark.asyncio
async def test_position_delete_records_zero_quantity_state(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Removal History"},
        headers=headers,
    )

    assert create_response.status_code == 201
    portfolio_id = create_response.json()["portfolio_id"]

    position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "5",
            "average_cost": "80",
        },
        headers=headers,
    )

    assert position_response.status_code == 200

    position_id = position_response.json()["position_id"]

    delete_response = await client.delete(
        f"/portfolios/{portfolio_id}/positions/{position_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    result = await db_session.execute(
        select(PortfolioPositionHistoryRecord)
        .where(
            PortfolioPositionHistoryRecord.portfolio_id == portfolio_id,
            PortfolioPositionHistoryRecord.instrument_id == instrument.id,
        )
        .order_by(PortfolioPositionHistoryRecord.sequence_id)
    )

    history = list(result.scalars())

    assert len(history) == 2

    assert history[0].event_type == "created"
    assert history[0].quantity == Decimal("5")
    assert history[0].average_cost == Decimal("80")

    assert history[1].event_type == "deleted"
    assert history[1].quantity == Decimal("0")
    assert history[1].average_cost == Decimal("80")

    assert history[0].sequence_id < history[1].sequence_id

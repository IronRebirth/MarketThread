from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.instrument import Instrument
from app.db.models.user import User


async def create_authenticated_user(
    client: AsyncClient,
) -> tuple[str, str]:
    email = f"portfolio-test-{uuid4().hex}@example.com"
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
    is_active: bool = True,
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=f"PORTTEST-{uuid4().hex[:8].upper()}",
        name="Portfolio Test Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=is_active,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


@pytest.fixture(autouse=True)
async def clean_portfolio_test_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("portfolio-test-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("PORTTEST-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_portfolios_require_authentication(
    client: AsyncClient,
) -> None:
    get_response = await client.get("/portfolios")

    assert get_response.status_code == 401

    post_response = await client.post(
        "/portfolios",
        json={"name": "Core"},
    )

    assert post_response.status_code == 401


@pytest.mark.asyncio
async def test_create_and_list_portfolios(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Core Holdings"},
        headers=headers,
    )

    assert create_response.status_code == 201

    body = create_response.json()

    assert body["name"] == "Core Holdings"
    assert body["position_count"] == 0
    assert body["portfolio_id"]

    list_response = await client.get(
        "/portfolios",
        headers=headers,
    )

    assert list_response.status_code == 200

    portfolios = list_response.json()

    assert len(portfolios) == 1
    assert portfolios[0]["portfolio_id"] == body["portfolio_id"]
    assert portfolios[0]["name"] == "Core Holdings"
    assert portfolios[0]["position_count"] == 0


@pytest.mark.asyncio
async def test_blank_portfolio_name_is_rejected(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)

    response = await client.post(
        "/portfolios",
        json={"name": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_portfolio_name_returns_conflict(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    first_response = await client.post(
        "/portfolios",
        json={"name": "Technology"},
        headers=headers,
    )

    assert first_response.status_code == 201

    second_response = await client.post(
        "/portfolios",
        json={"name": "Technology"},
        headers=headers,
    )

    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_portfolio_name_is_scoped_per_user(
    client: AsyncClient,
) -> None:
    _, first_token = await create_authenticated_user(client)
    _, second_token = await create_authenticated_user(client)

    first_response = await client.post(
        "/portfolios",
        json={"name": "Shared Name"},
        headers={"Authorization": f"Bearer {first_token}"},
    )

    second_response = await client.post(
        "/portfolios",
        json={"name": "Shared Name"},
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201


@pytest.mark.asyncio
async def test_portfolio_ownership_isolation(
    client: AsyncClient,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Private"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    get_response = await client.get(
        f"/portfolios/{portfolio_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert get_response.status_code == 404

    delete_response = await client.delete(
        f"/portfolios/{portfolio_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_upsert_position_and_get_portfolio_detail(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Core"},
        headers=headers,
    )

    assert create_response.status_code == 201

    portfolio_id = create_response.json()["portfolio_id"]

    position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "12.5",
            "average_cost": "125.40",
        },
        headers=headers,
    )

    assert position_response.status_code == 200

    position = position_response.json()

    assert position["portfolio_id"] == portfolio_id
    assert position["instrument_id"] == str(instrument.id)
    assert position["quantity"] == "12.50000000"
    assert position["average_cost"] == "125.40000000"
    assert position["symbol"] == instrument.symbol
    assert position["name"] == instrument.name
    assert position["currency"] == "USD"

    detail_response = await client.get(
        f"/portfolios/{portfolio_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200

    detail = detail_response.json()

    assert detail["position_count"] == 1
    assert len(detail["positions"]) == 1
    assert detail["positions"][0]["position_id"] == position["position_id"]


@pytest.mark.asyncio
async def test_position_upsert_replaces_existing_position(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Current State"},
        headers=headers,
    )

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

    first_position = first_response.json()
    second_position = second_response.json()

    assert second_position["position_id"] == first_position["position_id"]
    assert second_position["quantity"] == "25.00000000"
    assert second_position["average_cost"] == "110.00000000"

    detail_response = await client.get(
        f"/portfolios/{portfolio_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["position_count"] == 1


@pytest.mark.asyncio
async def test_inactive_instrument_cannot_be_added_to_portfolio(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(
        db_session,
        is_active=False,
    )

    create_response = await client.post(
        "/portfolios",
        json={"name": "Inactive"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "10",
            "average_cost": "100",
        },
        headers=headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_nonexistent_instrument_returns_not_found(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Missing Instrument"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{uuid4()}",
        json={
            "quantity": "10",
            "average_cost": "100",
        },
        headers=headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_zero_quantity_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Validation"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "0",
            "average_cost": "100",
        },
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_remove_portfolio_position(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Removable"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "5",
            "average_cost": "80",
        },
        headers=headers,
    )

    position_id = position_response.json()["position_id"]

    delete_response = await client.delete(
        f"/portfolios/{portfolio_id}/positions/{position_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    detail_response = await client.get(
        f"/portfolios/{portfolio_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["position_count"] == 0
    assert detail_response.json()["positions"] == []


@pytest.mark.asyncio
async def test_other_user_cannot_delete_position(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/portfolios",
        json={"name": "Protected"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    portfolio_id = create_response.json()["portfolio_id"]

    position_response = await client.put(
        f"/portfolios/{portfolio_id}/positions/{instrument.id}",
        json={
            "quantity": "5",
            "average_cost": "80",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    position_id = position_response.json()["position_id"]

    delete_response = await client.delete(
        f"/portfolios/{portfolio_id}/positions/{position_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_portfolio(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/portfolios",
        json={"name": "Delete Me"},
        headers=headers,
    )

    portfolio_id = create_response.json()["portfolio_id"]

    delete_response = await client.delete(
        f"/portfolios/{portfolio_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    get_response = await client.get(
        f"/portfolios/{portfolio_id}",
        headers=headers,
    )

    assert get_response.status_code == 404

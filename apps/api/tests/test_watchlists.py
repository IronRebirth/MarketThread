from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.instrument import Instrument
from app.db.models.user import User


async def create_authenticated_user(
    client: AsyncClient,
) -> tuple[str, str]:
    email = f"watchlist-test-{uuid4().hex}@example.com"
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
    is_active: bool = True,
) -> Instrument:
    instrument = Instrument(
        id=uuid4(),
        symbol=f"WTLSTEST-{uuid4().hex[:8].upper()}",
        name="Watchlist Test Instrument",
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
async def clean_watchlist_test_data(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        delete(User).where(
            User.email.like("watchlist-test-%@example.com"),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.symbol.like("WTLSTEST-%"),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_watchlists_require_authentication(
    client: AsyncClient,
) -> None:
    get_response = await client.get("/watchlists")

    assert get_response.status_code == 401

    post_response = await client.post(
        "/watchlists",
        json={"name": "Core"},
    )

    assert post_response.status_code == 401


@pytest.mark.asyncio
async def test_create_and_list_watchlists(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)

    create_response = await client.post(
        "/watchlists",
        json={"name": "Core Holdings"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert create_response.status_code == 201

    body = create_response.json()

    assert body["name"] == "Core Holdings"
    assert body["item_count"] == 0
    assert body["watchlist_id"]

    list_response = await client.get(
        "/watchlists",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert list_response.status_code == 200

    watchlists = list_response.json()

    assert len(watchlists) == 1
    assert watchlists[0]["watchlist_id"] == body["watchlist_id"]
    assert watchlists[0]["name"] == "Core Holdings"
    assert watchlists[0]["item_count"] == 0


@pytest.mark.asyncio
async def test_blank_watchlist_name_is_rejected(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)

    response = await client.post(
        "/watchlists",
        json={"name": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_watchlist_name_returns_conflict(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    first_response = await client.post(
        "/watchlists",
        json={"name": "Technology"},
        headers=headers,
    )

    assert first_response.status_code == 201

    second_response = await client.post(
        "/watchlists",
        json={"name": "Technology"},
        headers=headers,
    )

    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_watchlist_ownership_isolation(
    client: AsyncClient,
) -> None:
    _, owner_token = await create_authenticated_user(client)
    _, other_token = await create_authenticated_user(client)

    create_response = await client.post(
        "/watchlists",
        json={"name": "Private"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert create_response.status_code == 201

    watchlist_id = create_response.json()["watchlist_id"]

    get_response = await client.get(
        f"/watchlists/{watchlist_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert get_response.status_code == 404

    delete_response = await client.delete(
        f"/watchlists/{watchlist_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert delete_response.status_code == 404


@pytest.mark.asyncio
async def test_add_watchlist_item_and_get_detail(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_watchlist_response = await client.post(
        "/watchlists",
        json={"name": "Signals"},
        headers=headers,
    )

    assert create_watchlist_response.status_code == 201

    watchlist_id = create_watchlist_response.json()["watchlist_id"]

    add_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert add_response.status_code == 201

    item = add_response.json()

    assert item["watchlist_id"] == watchlist_id
    assert item["instrument_id"] == str(instrument.id)
    assert item["symbol"] == instrument.symbol
    assert item["name"] == instrument.name
    assert item["exchange"] == instrument.exchange
    assert item["is_active"] is True

    detail_response = await client.get(
        f"/watchlists/{watchlist_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200

    detail = detail_response.json()

    assert detail["item_count"] == 1
    assert len(detail["items"]) == 1
    assert detail["items"][0]["item_id"] == item["item_id"]


@pytest.mark.asyncio
async def test_duplicate_watchlist_item_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/watchlists",
        json={"name": "Idempotent"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    first_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    second_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.json()["item_id"] == first_response.json()["item_id"]

    items_response = await client.get(
        f"/watchlists/{watchlist_id}/items",
        headers=headers,
    )

    assert items_response.status_code == 200
    assert len(items_response.json()) == 1


@pytest.mark.asyncio
async def test_inactive_instrument_cannot_be_added(
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
        "/watchlists",
        json={"name": "Inactive"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
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
        "/watchlists",
        json={"name": "Missing Instrument"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(uuid4())},
        headers=headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_remove_watchlist_item(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    instrument = await create_test_instrument(db_session)

    create_response = await client.post(
        "/watchlists",
        json={"name": "Removable"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    add_response = await client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"instrument_id": str(instrument.id)},
        headers=headers,
    )

    item_id = add_response.json()["item_id"]

    delete_response = await client.delete(
        f"/watchlists/{watchlist_id}/items/{item_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    detail_response = await client.get(
        f"/watchlists/{watchlist_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["item_count"] == 0
    assert detail_response.json()["items"] == []


@pytest.mark.asyncio
async def test_delete_watchlist(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/watchlists",
        json={"name": "Delete Me"},
        headers=headers,
    )

    watchlist_id = create_response.json()["watchlist_id"]

    delete_response = await client.delete(
        f"/watchlists/{watchlist_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    get_response = await client.get(
        f"/watchlists/{watchlist_id}",
        headers=headers,
    )

    assert get_response.status_code == 404

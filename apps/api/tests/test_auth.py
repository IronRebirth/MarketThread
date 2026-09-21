from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.user import User

TEST_EMAIL = "auth-test@example.com"
TEST_PASSWORD = "StrongPassword123"


@pytest.fixture(autouse=True)
async def clean_auth_user(db_session: AsyncSession) -> None:
    """Remove the test user before each authentication test."""

    await db_session.execute(
        delete(User).where(User.email == TEST_EMAIL),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert UUID(body["id"])
    assert body["email"] == TEST_EMAIL
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_duplicate_registration_returns_conflict(
    client: AsyncClient,
) -> None:
    first_response = await client.post(
        "/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert first_response.status_code == 201

    second_response = await client.post(
        "/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_access_token(
    client: AsyncClient,
) -> None:
    await client.post(
        "/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    response = await client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(
    client: AsyncClient,
) -> None:
    await client.post(
        "/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    response = await client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get("/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(
    client: AsyncClient,
) -> None:
    await client.post(
        "/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    token = login_response.json()["access_token"]

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == TEST_EMAIL


@pytest.mark.asyncio
async def test_me_rejects_invalid_token(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_password_is_hashed() -> None:
    hashed = hash_password(TEST_PASSWORD)

    assert hashed != TEST_PASSWORD
    assert hashed.startswith("$argon2")


@pytest.mark.asyncio
async def test_logout_invalidates_existing_access_token(
    client: AsyncClient,
) -> None:
    await client.post(
        "/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )
    token = login_response.json()["access_token"]

    logout_response = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert logout_response.status_code == 204

    me_response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_access_token_contains_required_claims(
    client: AsyncClient,
) -> None:
    await client.post(
        "/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    token = login_response.json()["access_token"]

    from app.core.security import decode_access_token

    payload = decode_access_token(token)

    assert payload["typ"] == "access"
    assert payload["iss"] == "marketthread-api"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]
    assert payload["sv"] == 0

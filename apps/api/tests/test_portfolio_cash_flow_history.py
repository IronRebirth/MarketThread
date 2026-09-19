from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.portfolio_cash_flow import PortfolioCashFlowRecord

TEST_PASSWORD = "StrongPassword123"


async def create_authenticated_user(
    client: AsyncClient,
) -> str:
    email = f"cash-flow-test-{uuid4().hex}@example.com"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert register_response.status_code == 201

    login_response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    return login_response.json()["access_token"]


async def create_portfolio(
    client: AsyncClient,
    token: str,
) -> str:
    response = await client.post(
        "/portfolios",
        json={"name": f"Cash Flow {uuid4().hex[:8]}"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201

    return response.json()["portfolio_id"]


async def delete_portfolio(
    client: AsyncClient,
    token: str,
    portfolio_id: str,
) -> None:
    response = await client.delete(
        f"/portfolios/{portfolio_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_cash_flow_create_and_list_are_append_only_history(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token = await create_authenticated_user(client)
    portfolio_id = await create_portfolio(client, token)

    headers = {"Authorization": f"Bearer {token}"}

    earlier = datetime(
        2026,
        1,
        10,
        12,
        0,
        tzinfo=UTC,
    )
    later = datetime(
        2026,
        1,
        12,
        12,
        0,
        tzinfo=UTC,
    )

    deposit_response = await client.post(
        f"/portfolios/{portfolio_id}/cash-flows",
        json={
            "event_type": "deposit",
            "currency": "usd",
            "amount": "1000",
            "effective_at": later.isoformat(),
        },
        headers=headers,
    )

    withdrawal_response = await client.post(
        f"/portfolios/{portfolio_id}/cash-flows",
        json={
            "event_type": "withdrawal",
            "currency": "USD",
            "amount": "250",
            "effective_at": earlier.isoformat(),
        },
        headers=headers,
    )

    assert deposit_response.status_code == 201
    assert withdrawal_response.status_code == 201

    deposit = deposit_response.json()
    withdrawal = withdrawal_response.json()

    assert deposit["currency"] == "USD"
    assert Decimal(deposit["amount"]) == Decimal("1000")
    assert deposit["event_type"] == "deposit"
    assert deposit["effective_at"].startswith("2026-01-12T12:00:00")

    assert withdrawal["currency"] == "USD"
    assert Decimal(withdrawal["amount"]) == Decimal("250")
    assert withdrawal["event_type"] == "withdrawal"
    assert withdrawal["effective_at"].startswith("2026-01-10T12:00:00")

    # sequence_id records append/creation order, independent of effective_at.
    assert deposit["sequence_id"] < withdrawal["sequence_id"]

    list_response = await client.get(
        f"/portfolios/{portfolio_id}/cash-flows",
        headers=headers,
    )

    assert list_response.status_code == 200

    events = list_response.json()

    assert len(events) == 2
    assert [event["event_type"] for event in events] == [
        "withdrawal",
        "deposit",
    ]
    assert events[0]["effective_at"].startswith("2026-01-10T12:00:00")
    assert events[1]["effective_at"].startswith("2026-01-12T12:00:00")

    # The API sorts history by effective_at, not by append sequence.
    assert events[0]["sequence_id"] == withdrawal["sequence_id"]
    assert events[1]["sequence_id"] == deposit["sequence_id"]

    result = await db_session.execute(
        select(PortfolioCashFlowRecord)
        .where(
            PortfolioCashFlowRecord.portfolio_id == portfolio_id,
        )
        .order_by(
            PortfolioCashFlowRecord.sequence_id,
        ),
    )

    rows = list(result.scalars())

    assert len(rows) == 2
    assert rows[0].amount == Decimal("1000")
    assert rows[0].event_type == "deposit"
    assert rows[1].amount == Decimal("250")
    assert rows[1].event_type == "withdrawal"

    assert rows[0].recorded_at is not None
    assert rows[1].recorded_at is not None

    await delete_portfolio(
        client,
        token,
        portfolio_id,
    )


@pytest.mark.asyncio
async def test_cash_flow_list_supports_an_effective_time_window(
    client: AsyncClient,
) -> None:
    token = await create_authenticated_user(client)
    portfolio_id = await create_portfolio(client, token)

    headers = {"Authorization": f"Bearer {token}"}

    timestamps = (
        datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
        datetime(2026, 2, 5, 12, 0, tzinfo=UTC),
        datetime(2026, 2, 10, 12, 0, tzinfo=UTC),
    )

    for timestamp, event_type in zip(
        timestamps,
        ("deposit", "withdrawal", "deposit"),
        strict=True,
    ):
        response = await client.post(
            f"/portfolios/{portfolio_id}/cash-flows",
            json={
                "event_type": event_type,
                "currency": "USD",
                "amount": "100",
                "effective_at": timestamp.isoformat(),
            },
            headers=headers,
        )

        assert response.status_code == 201

    response = await client.get(
        f"/portfolios/{portfolio_id}/cash-flows",
        params={
            "start_at": timestamps[0].isoformat(),
            "end_at": timestamps[1].isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 200

    events = response.json()

    assert len(events) == 2
    assert [event["event_type"] for event in events] == [
        "deposit",
        "withdrawal",
    ]

    await delete_portfolio(
        client,
        token,
        portfolio_id,
    )


@pytest.mark.asyncio
async def test_cash_flow_history_is_isolated_between_users(
    client: AsyncClient,
) -> None:
    owner_token = await create_authenticated_user(client)
    other_token = await create_authenticated_user(client)

    portfolio_id = await create_portfolio(
        client,
        owner_token,
    )

    response = await client.post(
        f"/portfolios/{portfolio_id}/cash-flows",
        json={
            "event_type": "deposit",
            "currency": "USD",
            "amount": "500",
            "effective_at": datetime(
                2026,
                3,
                1,
                12,
                0,
                tzinfo=UTC,
            ).isoformat(),
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 201

    other_response = await client.get(
        f"/portfolios/{portfolio_id}/cash-flows",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert other_response.status_code == 404

    other_create_response = await client.post(
        f"/portfolios/{portfolio_id}/cash-flows",
        json={
            "event_type": "deposit",
            "currency": "USD",
            "amount": "100",
            "effective_at": datetime(
                2026,
                3,
                1,
                13,
                0,
                tzinfo=UTC,
            ).isoformat(),
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert other_create_response.status_code == 404

    await delete_portfolio(
        client,
        owner_token,
        portfolio_id,
    )


@pytest.mark.asyncio
async def test_cash_flow_rejects_invalid_amount_and_naive_timestamp(
    client: AsyncClient,
) -> None:
    token = await create_authenticated_user(client)
    portfolio_id = await create_portfolio(client, token)

    headers = {"Authorization": f"Bearer {token}"}

    invalid_amount_response = await client.post(
        f"/portfolios/{portfolio_id}/cash-flows",
        json={
            "event_type": "deposit",
            "currency": "USD",
            "amount": "0",
            "effective_at": datetime(
                2026,
                4,
                1,
                12,
                0,
                tzinfo=UTC,
            ).isoformat(),
        },
        headers=headers,
    )

    assert invalid_amount_response.status_code == 422

    naive_timestamp_response = await client.post(
        f"/portfolios/{portfolio_id}/cash-flows",
        json={
            "event_type": "deposit",
            "currency": "USD",
            "amount": "100",
            "effective_at": "2026-04-01T12:00:00",
        },
        headers=headers,
    )

    assert naive_timestamp_response.status_code == 422

    await delete_portfolio(
        client,
        token,
        portfolio_id,
    )


@pytest.mark.asyncio
async def test_cash_flow_query_rejects_reverse_time_window(
    client: AsyncClient,
) -> None:
    token = await create_authenticated_user(client)
    portfolio_id = await create_portfolio(client, token)

    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/portfolios/{portfolio_id}/cash-flows",
        params={
            "start_at": "2026-05-10T12:00:00+00:00",
            "end_at": "2026-05-01T12:00:00+00:00",
        },
        headers=headers,
    )

    assert response.status_code == 422

    await delete_portfolio(
        client,
        token,
        portfolio_id,
    )

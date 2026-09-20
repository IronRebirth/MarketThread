import os
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.notification_email_delivery import (
    NotificationEmailDeliveryRecord,
)
from app.notifications.email_service import (
    EmailDeliveryConfigurationError,
    NotificationEmailService,
)
from tests.test_watchlist_notifications import (
    create_authenticated_user,
    create_market_impact,
    create_watchlist_with_rule,
)


async def create_notification(
    client: AsyncClient,
    db_session: AsyncSession,
    headers: dict[str, str],
) -> str:
    _, instrument = await create_watchlist_with_rule(
        client,
        db_session,
        headers=headers,
        rule_name="Email notification",
    )

    await create_market_impact(
        db_session,
        ticker=instrument.symbol,
    )

    response = await client.post(
        "/notifications/sync",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["created_count"] == 1

    notifications_response = await client.get(
        "/notifications",
        headers=headers,
    )

    assert notifications_response.status_code == 200

    return notifications_response.json()["notifications"][0]["notification_id"]


@pytest.mark.asyncio
async def test_email_preferences_default_to_disabled(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        "/notifications/email/preferences",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"enabled": False}


@pytest.mark.asyncio
async def test_email_preferences_can_be_enabled_and_disabled(
    client: AsyncClient,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    enable_response = await client.patch(
        "/notifications/email/preferences",
        json={"enabled": True},
        headers=headers,
    )

    assert enable_response.status_code == 200
    assert enable_response.json() == {"enabled": True}

    disable_response = await client.patch(
        "/notifications/email/preferences",
        json={"enabled": False},
        headers=headers,
    )

    assert disable_response.status_code == 200
    assert disable_response.json() == {"enabled": False}


@pytest.mark.asyncio
async def test_disabled_email_dispatch_does_not_send(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    await create_notification(
        client,
        db_session,
        headers,
    )

    response = await client.post(
        "/notifications/email/dispatch",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "eligible_count": 0,
        "sent_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
    }


@pytest.mark.asyncio
async def test_enabled_dispatch_sends_once_and_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    notification_id = await create_notification(
        client,
        db_session,
        headers,
    )

    preference_response = await client.patch(
        "/notifications/email/preferences",
        json={"enabled": True},
        headers=headers,
    )
    assert preference_response.status_code == 200

    calls: list[tuple[str, str]] = []

    def fake_send(
        self: NotificationEmailService,
        *,
        recipient_email: str,
        notification,
    ) -> None:
        calls.append((recipient_email, str(notification.notification_id)))

    monkeypatch.setattr(NotificationEmailService, "send", fake_send)

    first_response = await client.post(
        "/notifications/email/dispatch",
        headers=headers,
    )
    second_response = await client.post(
        "/notifications/email/dispatch",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert first_response.json() == {
        "enabled": True,
        "eligible_count": 1,
        "sent_count": 1,
        "skipped_count": 0,
        "failed_count": 0,
    }

    assert second_response.status_code == 200
    assert second_response.json() == {
        "enabled": True,
        "eligible_count": 0,
        "sent_count": 0,
        "skipped_count": 1,
        "failed_count": 0,
    }

    assert calls == [(email, notification_id)]

    delivery = await db_session.scalar(
        select(NotificationEmailDeliveryRecord).where(
            NotificationEmailDeliveryRecord.notification_id == UUID(notification_id),
        ),
    )

    assert delivery is not None
    assert delivery.status == "sent"
    assert delivery.attempt_count == 1
    assert delivery.last_error is None
    assert delivery.sent_at is not None


@pytest.mark.asyncio
async def test_failed_email_delivery_is_recorded_for_retry(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, token = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    notification_id = await create_notification(
        client,
        db_session,
        headers,
    )

    preference_response = await client.patch(
        "/notifications/email/preferences",
        json={"enabled": True},
        headers=headers,
    )
    assert preference_response.status_code == 200

    def fake_send(
        self: NotificationEmailService,
        *,
        recipient_email: str,
        notification,
    ) -> None:
        raise EmailDeliveryConfigurationError("SMTP_HOST is not configured.")

    monkeypatch.setattr(NotificationEmailService, "send", fake_send)

    response = await client.post(
        "/notifications/email/dispatch",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "eligible_count": 1,
        "sent_count": 0,
        "skipped_count": 0,
        "failed_count": 1,
    }

    delivery = await db_session.scalar(
        select(NotificationEmailDeliveryRecord).where(
            NotificationEmailDeliveryRecord.notification_id == UUID(notification_id),
        ),
    )

    assert delivery is not None
    assert delivery.status == "failed"
    assert delivery.attempt_count == 1
    assert delivery.last_error == "SMTP_HOST is not configured."


def test_blank_smtp_environment_values_use_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_PORT", "")
    settings = Settings(
        _env_file=None,
    )

    assert settings.smtp_port == 587

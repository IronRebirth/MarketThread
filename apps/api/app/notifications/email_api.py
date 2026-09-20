from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.core.config import get_settings
from app.db.session import get_db_session
from app.notifications.email_persistence import (
    NotificationEmailDeliveryPersistenceService,
)
from app.notifications.email_schemas import (
    EmailNotificationDispatchResponse,
    EmailNotificationPreferencesResponse,
    EmailNotificationPreferencesUpdateRequest,
)
from app.notifications.email_service import (
    EmailDeliveryConfigurationError,
    EmailDeliveryError,
    NotificationEmailService,
)
from app.watchlists.notification_persistence import (
    WatchlistNotificationPersistenceService,
)

router = APIRouter(
    prefix="/notifications/email",
    tags=["notification email"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get(
    "/preferences",
    response_model=EmailNotificationPreferencesResponse,
)
async def get_email_preferences(
    current_user: CurrentUser,
) -> EmailNotificationPreferencesResponse:
    """Return the authenticated user's email notification preference."""

    return EmailNotificationPreferencesResponse(
        enabled=current_user.email_notifications_enabled,
    )


@router.patch(
    "/preferences",
    response_model=EmailNotificationPreferencesResponse,
)
async def update_email_preferences(
    payload: EmailNotificationPreferencesUpdateRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> EmailNotificationPreferencesResponse:
    """Update the authenticated user's email notification preference."""

    current_user.email_notifications_enabled = payload.enabled

    await session.commit()
    await session.refresh(current_user)

    return EmailNotificationPreferencesResponse(
        enabled=current_user.email_notifications_enabled,
    )


@router.post(
    "/dispatch",
    response_model=EmailNotificationDispatchResponse,
)
async def dispatch_email_notifications(
    current_user: CurrentUser,
    session: DatabaseSession,
) -> EmailNotificationDispatchResponse:
    """Deliver eligible notifications through the configured SMTP service."""

    if not current_user.email_notifications_enabled:
        return EmailNotificationDispatchResponse(
            enabled=False,
            eligible_count=0,
            sent_count=0,
            skipped_count=0,
            failed_count=0,
        )

    notification_service = WatchlistNotificationPersistenceService(session)

    notifications = await notification_service.list_for_user(
        user_id=current_user.id,
        limit=100,
    )

    delivery_persistence = NotificationEmailDeliveryPersistenceService(
        session,
    )
    email_service = NotificationEmailService(get_settings())

    eligible_count = 0
    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for notification in notifications:
        delivery = await delivery_persistence.claim_for_send(
            user_id=current_user.id,
            notification=notification,
            recipient_email=current_user.email,
        )

        if delivery is None:
            skipped_count += 1
            continue

        eligible_count += 1

        try:
            email_service.send(
                recipient_email=current_user.email,
                notification=notification,
            )
        except (
            EmailDeliveryConfigurationError,
            EmailDeliveryError,
        ) as exc:
            await delivery_persistence.record_failure(
                user_id=current_user.id,
                notification_id=notification.notification_id,
                error_message=str(exc),
            )
            failed_count += 1
        else:
            await delivery_persistence.record_success(
                user_id=current_user.id,
                notification_id=notification.notification_id,
            )
            sent_count += 1

    return EmailNotificationDispatchResponse(
        enabled=True,
        eligible_count=eligible_count,
        sent_count=sent_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
    )

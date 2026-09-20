from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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

    eligible_persistence = NotificationEmailDeliveryPersistenceService(
        session,
    )
    eligible_notifications = await eligible_persistence.list_eligible(
        user_id=current_user.id,
        notification_ids=tuple(
            notification.notification_id
            for notification in notifications
        ),
        recipient_email=current_user.email,
    )

    email_service = NotificationEmailService(get_settings())

    sent_count = 0
    skipped_count = len(notifications) - len(eligible_notifications)
    failed_count = 0

    for notification in eligible_notifications:
        await eligible_persistence.ensure_delivery(
            user_id=current_user.id,
            notification=notification,
            recipient_email=current_user.email,
        )

        try:
            email_service.send(
                recipient_email=current_user.email,
                notification=notification,
            )
        except (
            EmailDeliveryConfigurationError,
            EmailDeliveryError,
        ) as exc:
            await eligible_persistence.record_failure(
                user_id=current_user.id,
                notification_id=notification.notification_id,
                error_message=str(exc),
            )
            failed_count += 1
        else:
            await eligible_persistence.record_success(
                user_id=current_user.id,
                notification_id=notification.notification_id,
            )
            sent_count += 1

    return EmailNotificationDispatchResponse(
        enabled=True,
        eligible_count=len(eligible_notifications),
        sent_count=sent_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
    )

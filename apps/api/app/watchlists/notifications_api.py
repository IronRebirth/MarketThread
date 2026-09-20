from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.db.models.watchlist import WatchlistRecord
from app.db.session import get_db_session
from app.watchlists.alert_rule_persistence import (
    WatchlistAlertRulePersistenceService,
)
from app.watchlists.alerts import WatchlistAlertService
from app.watchlists.notification_models import (
    WatchlistNotification,
)
from app.watchlists.notification_persistence import (
    WatchlistNotificationNotFound,
    WatchlistNotificationPersistenceService,
)
from app.watchlists.notification_schemas import (
    WatchlistNotificationReadResponse,
    WatchlistNotificationsResponse,
    WatchlistNotificationResponse,
    WatchlistNotificationSyncResponse,
)
from app.watchlists.notifications import WatchlistNotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/sync",
    response_model=WatchlistNotificationSyncResponse,
)
async def sync_notifications(
    current_user: CurrentUser,
    session: DatabaseSession,
    assessed_at: datetime | None = Query(
        default=None,
        description="Optional timezone-aware assessment timestamp.",
    ),
) -> WatchlistNotificationSyncResponse:
    """Materialize new in-app notifications from current watchlist intelligence."""

    assessment_time = assessed_at or datetime.now(UTC)

    if assessment_time.tzinfo is None or assessment_time.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="assessed_at must be timezone-aware.",
        )

    assessment_time = assessment_time.astimezone(UTC)

    watchlist_result = await session.execute(
        select(WatchlistRecord.id)
        .where(WatchlistRecord.user_id == current_user.id)
        .order_by(WatchlistRecord.created_at.asc()),
    )

    watchlist_ids = tuple(watchlist_result.scalars().all())

    alert_rule_service = WatchlistAlertRulePersistenceService(session)
    alert_service = WatchlistAlertService(session)
    notification_service = WatchlistNotificationService()
    notification_persistence = WatchlistNotificationPersistenceService(session)

    created_count = 0
    matched_alert_count = 0
    existing_count = 0

    for watchlist_id in watchlist_ids:
        analysis = await alert_service.build(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
            assessed_at=assessment_time,
            limit=100,
        )

        rules = await alert_rule_service.list_for_user(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
        )

        pairs = notification_service.matching_pairs(
            alerts=analysis.alerts,
            rules=rules,
        )

        matched_alert_count += len({alert.alert_id for _, alert in pairs})

        existing_before = await notification_persistence.list_for_user(
            user_id=current_user.id,
            limit=100,
        )

        existing_keys_before = {
            (item.alert_rule_id, item.alert_id)
            for item in existing_before
        }

        notifications = await notification_persistence.materialize(
            user_id=current_user.id,
            matches=pairs,
        )

        created_count += sum(
            (
                notification.alert_rule_id,
                notification.alert_id,
            )
            not in existing_keys_before
            for notification in notifications
        )

    existing_count = max(
        0,
        matched_alert_count - created_count,
    )

    return WatchlistNotificationSyncResponse(
        created_count=created_count,
        existing_count=existing_count,
        matched_alert_count=matched_alert_count,
    )


@router.get(
    "",
    response_model=WatchlistNotificationsResponse,
)
async def list_notifications(
    current_user: CurrentUser,
    session: DatabaseSession,
    limit: int = Query(default=100, ge=1, le=100),
    unread_only: bool = False,
) -> WatchlistNotificationsResponse:
    """Return persisted in-app notifications for the authenticated user."""

    service = WatchlistNotificationPersistenceService(session)

    notifications = await service.list_for_user(
        user_id=current_user.id,
        limit=limit,
        unread_only=unread_only,
    )
    unread_count = await service.count_unread(user_id=current_user.id)

    return WatchlistNotificationsResponse(
        notifications=tuple(
            _to_response(notification)
            for notification in notifications
        ),
        returned_count=len(notifications),
        unread_count=unread_count,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=WatchlistNotificationReadResponse,
)
async def mark_notification_read(
    notification_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> WatchlistNotificationReadResponse:
    """Mark one authenticated user's notification as read."""

    service = WatchlistNotificationPersistenceService(session)

    try:
        notification = await service.mark_read(
            user_id=current_user.id,
            notification_id=notification_id,
        )
    except WatchlistNotificationNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        ) from None

    return WatchlistNotificationReadResponse(
        notification=_to_response(notification),
    )


def _to_response(
    notification: WatchlistNotification,
) -> WatchlistNotificationResponse:
    return WatchlistNotificationResponse(
        notification_id=notification.notification_id,
        watchlist_id=notification.watchlist_id,
        alert_rule_id=notification.alert_rule_id,
        alert_id=notification.alert_id,
        symbol=notification.symbol,
        rule_name=notification.rule_name,
        title=notification.title,
        message=notification.message,
        event_type=notification.event_type,
        direction=notification.direction,
        confidence=notification.confidence,
        created_at=notification.created_at,
        read_at=notification.read_at,
)

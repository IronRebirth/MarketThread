from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification_email_delivery import (
    NotificationEmailDeliveryRecord,
    NotificationEmailDeliveryStatus,
)
from app.db.models.watchlist_notification import WatchlistNotificationRecord
from app.notifications.email_models import NotificationEmailDelivery
from app.watchlists.notification_models import WatchlistNotification


class NotificationEmailDeliveryPersistenceService:
    """Persist and query idempotent notification email delivery state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_delivery(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> NotificationEmailDelivery | None:
        """Return delivery state for an owned notification."""

        result = await self.session.execute(
            select(NotificationEmailDeliveryRecord)
            .join(
                WatchlistNotificationRecord,
                WatchlistNotificationRecord.id
                == NotificationEmailDeliveryRecord.notification_id,
            )
            .where(
                WatchlistNotificationRecord.user_id == user_id,
                NotificationEmailDeliveryRecord.notification_id
                == notification_id,
            ),
        )

        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._delivery_to_domain(record)

    async def claim_for_send(
        self,
        *,
        user_id: UUID,
        notification: WatchlistNotification,
        recipient_email: str,
    ) -> NotificationEmailDelivery | None:
        """Lock one notification's delivery record and claim it for sending."""

        record_result = await self.session.execute(
            select(NotificationEmailDeliveryRecord)
            .join(
                WatchlistNotificationRecord,
                WatchlistNotificationRecord.id
                == NotificationEmailDeliveryRecord.notification_id,
            )
            .where(
                WatchlistNotificationRecord.user_id == user_id,
                NotificationEmailDeliveryRecord.notification_id
                == notification.notification_id,
            )
            .with_for_update(),
        )

        record = record_result.scalar_one_or_none()

        if record is None:
            await self.session.execute(
                insert(NotificationEmailDeliveryRecord)
                .values(
                    notification_id=notification.notification_id,
                    recipient_email=recipient_email,
                )
                .on_conflict_do_nothing(
                    index_elements=["notification_id"],
                ),
            )

            record_result = await self.session.execute(
                select(NotificationEmailDeliveryRecord)
                .join(
                    WatchlistNotificationRecord,
                    WatchlistNotificationRecord.id
                    == NotificationEmailDeliveryRecord.notification_id,
                )
                .where(
                    WatchlistNotificationRecord.user_id == user_id,
                    NotificationEmailDeliveryRecord.notification_id
                    == notification.notification_id,
                )
                .with_for_update(),
            )

            record = record_result.scalar_one_or_none()

        if record is None:
            await self.session.rollback()
            return None

        if record.status == NotificationEmailDeliveryStatus.SENT.value:
            await self.session.rollback()
            return None

        if record.recipient_email != recipient_email:
            record.recipient_email = recipient_email

        return self._delivery_to_domain(record)

    async def record_success(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> NotificationEmailDelivery:
        """Record one successful email delivery."""

        record = await self._get_owned_record(
            user_id=user_id,
            notification_id=notification_id,
        )

        if record is None:
            raise ValueError("Email delivery record does not exist.")

        record.status = NotificationEmailDeliveryStatus.SENT.value
        record.attempt_count += 1
        record.last_error = None
        record.sent_at = datetime.now(UTC)

        await self.session.commit()
        await self.session.refresh(record)

        return self._delivery_to_domain(record)

    async def record_failure(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
        error_message: str,
    ) -> NotificationEmailDelivery:
        """Record a failed email attempt without losing the notification."""

        record = await self._get_owned_record(
            user_id=user_id,
            notification_id=notification_id,
        )

        if record is None:
            raise ValueError("Email delivery record does not exist.")

        record.status = NotificationEmailDeliveryStatus.FAILED.value
        record.attempt_count += 1
        record.last_error = error_message[:4000]

        await self.session.commit()
        await self.session.refresh(record)

        return self._delivery_to_domain(record)

    async def _get_owned_record(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> NotificationEmailDeliveryRecord | None:
        result = await self.session.execute(
            select(NotificationEmailDeliveryRecord)
            .join(
                WatchlistNotificationRecord,
                WatchlistNotificationRecord.id
                == NotificationEmailDeliveryRecord.notification_id,
            )
            .where(
                WatchlistNotificationRecord.user_id == user_id,
                NotificationEmailDeliveryRecord.notification_id == notification_id,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    def _notification_to_domain(
        record: WatchlistNotificationRecord,
    ) -> WatchlistNotification:
        return WatchlistNotification(
            notification_id=record.id,
            user_id=record.user_id,
            watchlist_id=record.watchlist_id,
            alert_rule_id=record.alert_rule_id,
            alert_id=record.alert_id,
            symbol=record.symbol,
            rule_name=record.rule_name,
            title=record.title,
            message=record.message,
            event_type=record.event_type,
            direction=record.direction,
            confidence=record.confidence,
            created_at=record.created_at,
            read_at=record.read_at,
        )

    @staticmethod
    def _delivery_to_domain(
        record: NotificationEmailDeliveryRecord,
    ) -> NotificationEmailDelivery:
        return NotificationEmailDelivery(
            delivery_id=record.id,
            notification_id=record.notification_id,
            recipient_email=record.recipient_email,
            status=record.status,
            attempt_count=record.attempt_count,
            last_error=record.last_error,
            sent_at=record.sent_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

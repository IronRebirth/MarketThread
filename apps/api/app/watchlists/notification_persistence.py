from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.watchlist_notification import WatchlistNotificationRecord
from app.watchlists.alert_rule_models import WatchlistAlertRule
from app.watchlists.alerts_models import WatchlistAlert
from app.watchlists.notification_models import WatchlistNotification


class WatchlistNotificationNotFound(Exception):
    """Raised when an owned notification cannot be found."""


class WatchlistNotificationPersistenceService:
    """Persist and retrieve user-owned in-app watchlist notifications."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def materialize(
        self,
        *,
        user_id: UUID,
        matches: Sequence[tuple[WatchlistAlertRule, WatchlistAlert]],
    ) -> tuple[WatchlistNotification, ...]:
        """Insert missing notifications and return all matched notifications."""

        if not matches:
            return ()

        values = [
            self._to_insert_values(
                user_id=user_id,
                rule=rule,
                alert=alert,
            )
            for rule, alert in matches
        ]

        statement = (
            insert(WatchlistNotificationRecord)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=[
                    "user_id",
                    "alert_rule_id",
                    "alert_id",
                ],
            )
        )

        await self.session.execute(statement)
        await self.session.commit()

        pairs = tuple(
            (rule.alert_rule_id, alert.alert_id)
            for rule, alert in matches
        )

        notification_records = await self._get_records_for_pairs(
            user_id=user_id,
            pairs=pairs,
        )

        return tuple(
            self._to_domain(record)
            for record in notification_records
        )

    async def list_for_user(
        self,
        *,
        user_id: UUID,
        limit: int = 100,
        unread_only: bool = False,
    ) -> tuple[WatchlistNotification, ...]:
        """List persisted notifications belonging to one user."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        statement = (
            select(WatchlistNotificationRecord)
            .where(
                WatchlistNotificationRecord.user_id == user_id,
            )
            .order_by(
                WatchlistNotificationRecord.created_at.desc(),
                WatchlistNotificationRecord.id.desc(),
            )
            .limit(limit)
        )

        if unread_only:
            statement = statement.where(
                WatchlistNotificationRecord.read_at.is_(None),
            )

        result = await self.session.execute(statement)

        return tuple(
            self._to_domain(record)
            for record in result.scalars().all()
        )

    async def count_unread(
        self,
        *,
        user_id: UUID,
    ) -> int:
        """Count unread notifications belonging to one user."""

        result = await self.session.scalar(
            select(func.count(WatchlistNotificationRecord.id)).where(
                WatchlistNotificationRecord.user_id == user_id,
                WatchlistNotificationRecord.read_at.is_(None),
            ),
        )

        return int(result or 0)

    async def mark_read(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
        read_at: datetime | None = None,
    ) -> WatchlistNotification:
        """Mark one owned notification as read."""

        timestamp = read_at or datetime.now(UTC)

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("read_at must be timezone-aware")

        timestamp = timestamp.astimezone(UTC)

        record = await self.session.scalar(
            select(WatchlistNotificationRecord)
            .where(
                WatchlistNotificationRecord.id == notification_id,
                WatchlistNotificationRecord.user_id == user_id,
            )
            .with_for_update(),
        )

        if record is None:
            raise WatchlistNotificationNotFound

        if record.read_at is None:
            record.read_at = timestamp

            await self.session.commit()
            await self.session.refresh(record)

        return self._to_domain(record)

    async def _get_records_for_pairs(
        self,
        *,
        user_id: UUID,
        pairs: Sequence[tuple[UUID, UUID]],
    ) -> tuple[WatchlistNotificationRecord, ...]:
        if not pairs:
            return ()

        conditions = [
            (
                WatchlistNotificationRecord.alert_rule_id == rule_id,
                WatchlistNotificationRecord.alert_id == alert_id,
            )
            for rule_id, alert_id in pairs
        ]

        result = await self.session.execute(
            select(WatchlistNotificationRecord)
            .where(
                WatchlistNotificationRecord.user_id == user_id,
                *[condition[0] & condition[1] for condition in conditions],
            )
        )

        return tuple(result.scalars().all())

    @staticmethod
    def _to_insert_values(
        *,
        user_id: UUID,
        rule: WatchlistAlertRule,
        alert: WatchlistAlert,
    ) -> dict[str, object]:
        return {
            "user_id": user_id,
            "watchlist_id": alert.watchlist_id,
            "alert_rule_id": rule.rule_id,
            "alert_id": alert.alert_id,
            "symbol": alert.symbol,
            "rule_name": rule.name,
            "title": alert.title,
            "message": alert.explanation,
            "event_type": alert.event_type,
            "direction": alert.direction,
            "confidence": alert.confidence,
        }

    @staticmethod
    def _to_domain(
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

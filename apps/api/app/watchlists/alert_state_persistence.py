from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.watchlist import WatchlistRecord
from app.db.models.watchlist_alert_state import WatchlistAlertStateRecord
from app.watchlists.alert_state_models import (
    AlertStatus,
    WatchlistAlertState,
)
from app.watchlists.alerts_models import WatchlistAlert


class WatchlistAlertStateNotFound(Exception):
    """Raised when a requested alert state cannot be found."""


class WatchlistAlertStateTransitionError(Exception):
    """Raised when an alert state transition is invalid."""


class WatchlistAlertStatePersistenceService:
    """Persist and retrieve durable watchlist-alert interaction state."""

    _STATUS_ORDER = {
        AlertStatus.NEW: 0,
        AlertStatus.SEEN: 1,
        AlertStatus.ACKNOWLEDGED: 2,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_for_alerts(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
        alerts: Sequence[WatchlistAlert],
    ) -> tuple[WatchlistAlertState, ...]:
        """Create missing state rows idempotently and return their state."""

        watchlist_exists = await self.session.scalar(
            select(WatchlistRecord.id).where(
                WatchlistRecord.id == watchlist_id,
                WatchlistRecord.user_id == user_id,
            ),
        )

        if watchlist_exists is None:
            raise WatchlistAlertStateNotFound

        if not alerts:
            return ()

        values = [
            {
                "alert_id": alert.alert_id,
                "watchlist_id": alert.watchlist_id,
                "watchlist_item_id": alert.watchlist_item_id,
                "market_impact_id": alert.market_impact_id,
                "event_id": alert.event_id,
                "status": AlertStatus.NEW.value,
            }
            for alert in alerts
        ]

        statement = (
            insert(WatchlistAlertStateRecord)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=["alert_id"],
            )
        )

        await self.session.execute(statement)
        await self.session.commit()

        alert_ids = tuple(alert.alert_id for alert in alerts)

        result = await self.session.execute(
            select(WatchlistAlertStateRecord)
            .where(
                WatchlistAlertStateRecord.watchlist_id == watchlist_id,
                WatchlistAlertStateRecord.alert_id.in_(alert_ids),
            )
            .order_by(
                WatchlistAlertStateRecord.created_at.asc(),
                WatchlistAlertStateRecord.alert_id.asc(),
            ),
        )

        records = result.scalars().all()

        return tuple(self._to_domain(record) for record in records)

    async def update_status(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
        alert_id: UUID,
        status: AlertStatus,
        updated_at: datetime | None = None,
    ) -> WatchlistAlertState:
        """Advance an owned alert to a monotonic lifecycle state."""

        now = updated_at or datetime.now(UTC)

        if now.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")

        now = now.astimezone(UTC)

        statement = (
            select(WatchlistAlertStateRecord)
            .join(
                WatchlistRecord,
                WatchlistRecord.id == WatchlistAlertStateRecord.watchlist_id,
            )
            .where(
                WatchlistAlertStateRecord.alert_id == alert_id,
                WatchlistAlertStateRecord.watchlist_id == watchlist_id,
                WatchlistRecord.user_id == user_id,
            )
            .with_for_update()
        )

        record = await self.session.scalar(statement)

        if record is None:
            raise WatchlistAlertStateNotFound

        current_status = AlertStatus(record.status)

        if self._STATUS_ORDER[status] < self._STATUS_ORDER[current_status]:
            raise WatchlistAlertStateTransitionError(
                f"Cannot move alert from {current_status.value} "
                f"back to {status.value}.",
            )

        record.status = status.value
        record.updated_at = now

        if (
            status
            in (
                AlertStatus.SEEN,
                AlertStatus.ACKNOWLEDGED,
            )
            and record.seen_at is None
        ):
            record.seen_at = now

        if status == AlertStatus.ACKNOWLEDGED and record.acknowledged_at is None:
            record.acknowledged_at = now

        await self.session.commit()
        await self.session.refresh(record)

        return self._to_domain(record)

    async def get_for_alert(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
        alert_id: UUID,
    ) -> WatchlistAlertState:
        """Retrieve one owned persisted alert state."""

        statement = (
            select(WatchlistAlertStateRecord)
            .join(
                WatchlistRecord,
                WatchlistRecord.id == WatchlistAlertStateRecord.watchlist_id,
            )
            .where(
                WatchlistAlertStateRecord.alert_id == alert_id,
                WatchlistAlertStateRecord.watchlist_id == watchlist_id,
                WatchlistRecord.user_id == user_id,
            )
        )

        record = await self.session.scalar(statement)

        if record is None:
            raise WatchlistAlertStateNotFound

        return self._to_domain(record)

    async def list_for_watchlist(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
        status: AlertStatus | None = None,
    ) -> tuple[WatchlistAlertState, ...]:
        """List persisted alert states for an owned watchlist."""

        statement = (
            select(WatchlistAlertStateRecord)
            .join(
                WatchlistRecord,
                WatchlistRecord.id == WatchlistAlertStateRecord.watchlist_id,
            )
            .where(
                WatchlistAlertStateRecord.watchlist_id == watchlist_id,
                WatchlistRecord.user_id == user_id,
            )
            .order_by(
                WatchlistAlertStateRecord.created_at.desc(),
                WatchlistAlertStateRecord.alert_id.desc(),
            )
        )

        if status is not None:
            statement = statement.where(
                WatchlistAlertStateRecord.status == status.value,
            )

        result = await self.session.execute(statement)

        records = result.scalars().all()

        return tuple(self._to_domain(record) for record in records)

    @staticmethod
    def _to_domain(
        record: WatchlistAlertStateRecord,
    ) -> WatchlistAlertState:
        """Convert a persisted state record to its domain model."""

        return WatchlistAlertState(
            alert_id=record.alert_id,
            watchlist_id=record.watchlist_id,
            watchlist_item_id=record.watchlist_item_id,
            market_impact_id=record.market_impact_id,
            event_id=record.event_id,
            status=AlertStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            seen_at=record.seen_at,
            acknowledged_at=record.acknowledged_at,
        )

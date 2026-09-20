from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.watchlist import WatchlistRecord
from app.db.models.watchlist_alert_rule import WatchlistAlertRuleRecord
from app.watchlists.alert_rule_models import (
    AlertRuleType,
    WatchlistAlertRule,
    WatchlistAlertRuleConditions,
)


class WatchlistAlertRuleNotFound(Exception):
    """Raised when an owned watchlist or alert rule cannot be found."""


class WatchlistAlertRuleNameConflict(Exception):
    """Raised when a watchlist already owns a rule with the same name."""


class WatchlistAlertRulePersistenceService:
    """Database persistence for user-owned watchlist alert rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
        name: str,
        rule_type: AlertRuleType,
        conditions: WatchlistAlertRuleConditions,
        enabled: bool,
    ) -> WatchlistAlertRule:
        """Create one owned alert rule."""

        await self._require_watchlist(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        record = WatchlistAlertRuleRecord(
            watchlist_id=watchlist_id,
            name=name,
            rule_type=rule_type.value,
            conditions=conditions.model_dump(mode="json"),
            enabled=enabled,
        )

        self.session.add(record)

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()

            if await self._name_exists(
                watchlist_id=watchlist_id,
                name=name,
            ):
                raise WatchlistAlertRuleNameConflict from None

            raise

        await self.session.refresh(record)

        return self._to_domain(record)

    async def list_for_user(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> tuple[WatchlistAlertRule, ...]:
        """List all rules belonging to an owned watchlist."""

        await self._require_watchlist(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        result = await self.session.execute(
            select(WatchlistAlertRuleRecord)
            .where(
                WatchlistAlertRuleRecord.watchlist_id == watchlist_id,
            )
            .order_by(
                WatchlistAlertRuleRecord.created_at.asc(),
                WatchlistAlertRuleRecord.id.asc(),
            ),
        )

        return tuple(self._to_domain(record) for record in result.scalars().all())

    async def update(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
        rule_id: UUID,
        name: str | None = None,
        conditions: WatchlistAlertRuleConditions | None = None,
        enabled: bool | None = None,
    ) -> WatchlistAlertRule:
        """Update one owned alert rule."""

        record = await self._get_rule(
            user_id=user_id,
            watchlist_id=watchlist_id,
            rule_id=rule_id,
        )

        if record is None:
            raise WatchlistAlertRuleNotFound

        if name is not None:
            record.name = name

        if conditions is not None:
            record.conditions = conditions.model_dump(mode="json")

        if enabled is not None:
            record.enabled = enabled

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()

            if name is not None and await self._name_exists(
                watchlist_id=watchlist_id,
                name=name,
                exclude_rule_id=rule_id,
            ):
                raise WatchlistAlertRuleNameConflict from None

            raise

        await self.session.refresh(record)

        return self._to_domain(record)

    async def delete(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
        rule_id: UUID,
    ) -> bool:
        """Delete one owned alert rule."""

        record = await self._get_rule(
            user_id=user_id,
            watchlist_id=watchlist_id,
            rule_id=rule_id,
        )

        if record is None:
            raise WatchlistAlertRuleNotFound

        await self.session.delete(record)
        await self.session.commit()

        return True

    async def _get_rule(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
        rule_id: UUID,
    ) -> WatchlistAlertRuleRecord | None:
        statement = (
            select(WatchlistAlertRuleRecord)
            .join(
                WatchlistRecord,
                WatchlistRecord.id == WatchlistAlertRuleRecord.watchlist_id,
            )
            .where(
                WatchlistRecord.user_id == user_id,
                WatchlistAlertRuleRecord.watchlist_id == watchlist_id,
                WatchlistAlertRuleRecord.id == rule_id,
            )
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def _require_watchlist(
        self,
        *,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> None:
        result = await self.session.scalar(
            select(WatchlistRecord.id).where(
                WatchlistRecord.id == watchlist_id,
                WatchlistRecord.user_id == user_id,
            ),
        )

        if result is None:
            raise WatchlistAlertRuleNotFound

    async def _name_exists(
        self,
        *,
        watchlist_id: UUID,
        name: str,
        exclude_rule_id: UUID | None = None,
    ) -> bool:
        statement = select(WatchlistAlertRuleRecord.id).where(
            WatchlistAlertRuleRecord.watchlist_id == watchlist_id,
            WatchlistAlertRuleRecord.name == name,
        )

        if exclude_rule_id is not None:
            statement = statement.where(
                WatchlistAlertRuleRecord.id != exclude_rule_id,
            )

        return await self.session.scalar(statement) is not None

    @staticmethod
    def _to_domain(
        record: WatchlistAlertRuleRecord,
    ) -> WatchlistAlertRule:
        return WatchlistAlertRule(
            rule_id=record.id,
            watchlist_id=record.watchlist_id,
            name=record.name,
            rule_type=AlertRuleType(record.rule_type),
            conditions=WatchlistAlertRuleConditions.model_validate(
                record.conditions,
            ),
            enabled=record.enabled,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

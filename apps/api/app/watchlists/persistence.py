from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.instrument import Instrument
from app.db.models.watchlist import WatchlistItemRecord, WatchlistRecord
from app.watchlists.models import Watchlist, WatchlistDetail, WatchlistItem


class WatchlistPersistenceService:
    """Persistence operations for user-owned watchlists."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: UUID,
        name: str,
    ) -> Watchlist:
        record = WatchlistRecord(
            user_id=user_id,
            name=name,
        )

        self.session.add(record)

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise

        await self.session.refresh(record)

        return self._to_domain(record, item_count=0)

    async def list_for_user(
        self,
        user_id: UUID,
    ) -> tuple[Watchlist, ...]:
        statement = (
            select(
                WatchlistRecord,
                func.count(WatchlistItemRecord.id),
            )
            .outerjoin(
                WatchlistItemRecord,
                WatchlistItemRecord.watchlist_id == WatchlistRecord.id,
            )
            .where(WatchlistRecord.user_id == user_id)
            .group_by(WatchlistRecord.id)
            .order_by(
                WatchlistRecord.created_at.desc(),
                WatchlistRecord.id.desc(),
            )
        )

        result = await self.session.execute(statement)

        return tuple(
            self._to_domain(record, item_count=count)
            for record, count in result.all()
        )

    async def get_for_user(
        self,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> Watchlist | None:
        record = await self._get_record_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        if record is None:
            return None

        count_statement = select(func.count(WatchlistItemRecord.id)).where(
            WatchlistItemRecord.watchlist_id == watchlist_id,
        )

        count_result = await self.session.execute(count_statement)
        item_count = count_result.scalar_one()

        return self._to_domain(record, item_count=item_count)

    async def get_detail_for_user(
        self,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> WatchlistDetail | None:
        watchlist = await self.get_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        if watchlist is None:
            return None

        items = await self.list_items_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        return WatchlistDetail(
            **watchlist.model_dump(),
            items=items,
        )

    async def delete_for_user(
        self,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> bool:
        record = await self._get_record_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        if record is None:
            return False

        await self.session.delete(record)
        await self.session.commit()

        return True

    async def add_item(
        self,
        user_id: UUID,
        watchlist_id: UUID,
        instrument_id: UUID,
    ) -> tuple[WatchlistItem | None, bool]:
        watchlist = await self._get_record_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        if watchlist is None:
            return None, False

        instrument = await self.session.get(Instrument, instrument_id)

        if instrument is None or not instrument.is_active:
            return None, False

        existing_statement = (
            select(WatchlistItemRecord)
            .where(
                WatchlistItemRecord.watchlist_id == watchlist_id,
                WatchlistItemRecord.instrument_id == instrument_id,
            )
        )

        existing_result = await self.session.execute(existing_statement)
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            return self._to_item_domain(existing, instrument), False

        record = WatchlistItemRecord(
            watchlist_id=watchlist_id,
            instrument_id=instrument_id,
        )

        self.session.add(record)

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()

            raced_result = await self.session.execute(existing_statement)
            raced_record = raced_result.scalar_one_or_none()

            if raced_record is None:
                raise

            return (
                self._to_item_domain(raced_record, instrument),
                False,
            )

        await self.session.refresh(record)

        return self._to_item_domain(record, instrument), True

    async def list_items_for_user(
        self,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> tuple[WatchlistItem, ...]:
        statement = (
            select(WatchlistItemRecord, Instrument)
            .join(
                Instrument,
                Instrument.id == WatchlistItemRecord.instrument_id,
            )
            .join(
                WatchlistRecord,
                WatchlistRecord.id == WatchlistItemRecord.watchlist_id,
            )
            .where(
                WatchlistRecord.user_id == user_id,
                WatchlistItemRecord.watchlist_id == watchlist_id,
            )
            .order_by(
                WatchlistItemRecord.added_at.desc(),
                WatchlistItemRecord.id.desc(),
            )
        )

        result = await self.session.execute(statement)

        return tuple(
            self._to_item_domain(item, instrument)
            for item, instrument in result.all()
        )

    async def delete_item_for_user(
        self,
        user_id: UUID,
        watchlist_id: UUID,
        item_id: UUID,
    ) -> bool:
        statement = (
            select(WatchlistItemRecord)
            .join(
                WatchlistRecord,
                WatchlistRecord.id == WatchlistItemRecord.watchlist_id,
            )
            .where(
                WatchlistRecord.user_id == user_id,
                WatchlistItemRecord.watchlist_id == watchlist_id,
                WatchlistItemRecord.id == item_id,
            )
        )

        result = await self.session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None:
            return False

        await self.session.delete(record)
        await self.session.commit()

        return True

    async def _get_record_for_user(
        self,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> WatchlistRecord | None:
        statement = select(WatchlistRecord).where(
            WatchlistRecord.id == watchlist_id,
            WatchlistRecord.user_id == user_id,
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    @staticmethod
    def _to_domain(
        record: WatchlistRecord,
        item_count: int,
    ) -> Watchlist:
        return Watchlist(
            watchlist_id=record.id,
            user_id=record.user_id,
            name=record.name,
            created_at=record.created_at,
            updated_at=record.updated_at,
            item_count=item_count,
        )

    @staticmethod
    def _to_item_domain(
        record: WatchlistItemRecord,
        instrument: Instrument,
    ) -> WatchlistItem:
        return WatchlistItem(
            item_id=record.id,
            watchlist_id=record.watchlist_id,
            instrument_id=record.instrument_id,
            added_at=record.added_at,
            symbol=instrument.symbol,
            name=instrument.name,
            exchange=instrument.exchange,
            asset_class=instrument.asset_class,
            currency=instrument.currency,
            is_active=instrument.is_active,
        )

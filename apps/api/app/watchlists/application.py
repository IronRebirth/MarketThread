from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.watchlists.models import Watchlist, WatchlistDetail, WatchlistItem
from app.watchlists.persistence import WatchlistPersistenceService


class WatchlistNotFound(Exception):
    """Raised when an owned watchlist cannot be found."""


class WatchlistNameConflict(Exception):
    """Raised when the user already owns a watchlist with the same name."""


class WatchlistInstrumentNotFound(Exception):
    """Raised when an instrument cannot be added to a watchlist."""


class WatchlistItemNotFound(Exception):
    """Raised when a watchlist item cannot be found."""


class WatchlistApplicationService:
    """Application use cases for authenticated watchlists."""

    def __init__(self, session: AsyncSession):
        self.persistence = WatchlistPersistenceService(session)

    async def create(
        self,
        user_id: UUID,
        name: str,
    ) -> Watchlist:
        try:
            return await self.persistence.create(
                user_id=user_id,
                name=name,
            )
        except IntegrityError:
            raise WatchlistNameConflict from None

    async def list(
        self,
        user_id: UUID,
    ) -> tuple[Watchlist, ...]:
        return await self.persistence.list_for_user(user_id)

    async def get(
        self,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> WatchlistDetail:
        watchlist = await self.persistence.get_detail_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        if watchlist is None:
            raise WatchlistNotFound

        return watchlist

    async def delete(
        self,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> None:
        deleted = await self.persistence.delete_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        if not deleted:
            raise WatchlistNotFound

    async def add_item(
        self,
        user_id: UUID,
        watchlist_id: UUID,
        instrument_id: UUID,
    ) -> tuple[WatchlistItem, bool]:
        watchlist = await self.persistence.get_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        if watchlist is None:
            raise WatchlistNotFound

        item, created = await self.persistence.add_item(
            user_id=user_id,
            watchlist_id=watchlist_id,
            instrument_id=instrument_id,
        )

        if item is None:
            raise WatchlistInstrumentNotFound

        return item, created

    async def list_items(
        self,
        user_id: UUID,
        watchlist_id: UUID,
    ) -> tuple[WatchlistItem, ...]:
        watchlist = await self.persistence.get_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        if watchlist is None:
            raise WatchlistNotFound

        return await self.persistence.list_items_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

    async def remove_item(
        self,
        user_id: UUID,
        watchlist_id: UUID,
        item_id: UUID,
    ) -> None:
        watchlist = await self.persistence.get_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )

        if watchlist is None:
            raise WatchlistNotFound

        deleted = await self.persistence.delete_item_for_user(
            user_id=user_id,
            watchlist_id=watchlist_id,
            item_id=item_id,
        )

        if not deleted:
            raise WatchlistItemNotFound

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Watchlist(BaseModel):
    """Persisted user-owned watchlist."""

    model_config = ConfigDict(frozen=True)

    watchlist_id: UUID
    user_id: UUID
    name: str = Field(min_length=1, max_length=100)
    created_at: datetime
    updated_at: datetime
    item_count: int = Field(ge=0)


class WatchlistItem(BaseModel):
    """Instrument tracked by a watchlist."""

    model_config = ConfigDict(frozen=True)

    item_id: UUID
    watchlist_id: UUID
    instrument_id: UUID
    added_at: datetime
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    exchange: str = Field(min_length=1, max_length=64)
    asset_class: str = Field(min_length=1, max_length=32)
    currency: str = Field(min_length=1, max_length=3)
    is_active: bool


class WatchlistDetail(Watchlist):
    """Watchlist with its currently persisted items."""

    items: tuple[WatchlistItem, ...] = ()

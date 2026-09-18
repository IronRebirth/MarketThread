from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class WatchlistCreateRequest(BaseModel):
    """Request payload for creating a watchlist."""

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        name = value.strip()

        if not name:
            raise ValueError("Watchlist name cannot be blank.")

        return name


class WatchlistResponse(BaseModel):
    """Watchlist API representation."""

    watchlist_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    item_count: int


class WatchlistItemCreateRequest(BaseModel):
    """Request payload for adding an instrument to a watchlist."""

    instrument_id: UUID


class WatchlistItemResponse(BaseModel):
    """Watchlist item API representation."""

    item_id: UUID
    watchlist_id: UUID
    instrument_id: UUID
    added_at: datetime
    symbol: str
    name: str
    exchange: str
    asset_class: str
    currency: str
    is_active: bool


class WatchlistDetailResponse(WatchlistResponse):
    """Watchlist response including its tracked instruments."""

    items: list[WatchlistItemResponse]

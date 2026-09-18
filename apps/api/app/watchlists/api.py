from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.db.session import get_db_session
from app.watchlists.application import (
    WatchlistApplicationService,
    WatchlistInstrumentNotFound,
    WatchlistItemNotFound,
    WatchlistNameConflict,
    WatchlistNotFound,
)
from app.watchlists.schemas import (
    WatchlistCreateRequest,
    WatchlistDetailResponse,
    WatchlistItemCreateRequest,
    WatchlistItemResponse,
    WatchlistResponse,
)

router = APIRouter(prefix="/watchlists", tags=["watchlists"])

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_service(session: DatabaseSession) -> WatchlistApplicationService:
    return WatchlistApplicationService(session)


WatchlistService = Annotated[
    WatchlistApplicationService,
    Depends(get_service),
]


@router.post(
    "",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_watchlist(
    payload: WatchlistCreateRequest,
    current_user: CurrentUser,
    service: WatchlistService,
) -> WatchlistResponse:
    """Create a new authenticated user's watchlist."""

    try:
        watchlist = await service.create(
            user_id=current_user.id,
            name=payload.name,
        )
    except WatchlistNameConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A watchlist with this name already exists.",
        ) from None

    return WatchlistResponse(
        watchlist_id=watchlist.watchlist_id,
        name=watchlist.name,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        item_count=watchlist.item_count,
    )


@router.get(
    "",
    response_model=list[WatchlistResponse],
)
async def list_watchlists(
    current_user: CurrentUser,
    service: WatchlistService,
) -> list[WatchlistResponse]:
    """List the authenticated user's watchlists."""

    watchlists = await service.list(current_user.id)

    return [
        WatchlistResponse(
            watchlist_id=watchlist.watchlist_id,
            name=watchlist.name,
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at,
            item_count=watchlist.item_count,
        )
        for watchlist in watchlists
    ]


@router.post(
    "/{watchlist_id}/items",
    response_model=WatchlistItemResponse,
)
async def add_watchlist_item(
    watchlist_id: UUID,
    payload: WatchlistItemCreateRequest,
    response: Response,
    current_user: CurrentUser,
    service: WatchlistService,
) -> WatchlistItemResponse:
    """Add an instrument to a user's watchlist idempotently."""

    try:
        item, created = await service.add_item(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
            instrument_id=payload.instrument_id,
        )
    except WatchlistNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found.",
        ) from None
    except WatchlistInstrumentNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active instrument not found.",
        ) from None

    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK

    return WatchlistItemResponse(
        item_id=item.item_id,
        watchlist_id=item.watchlist_id,
        instrument_id=item.instrument_id,
        added_at=item.added_at,
        symbol=item.symbol,
        name=item.name,
        exchange=item.exchange,
        asset_class=item.asset_class,
        currency=item.currency,
        is_active=item.is_active,
    )


@router.get(
    "/{watchlist_id}/items",
    response_model=list[WatchlistItemResponse],
)
async def list_watchlist_items(
    watchlist_id: UUID,
    current_user: CurrentUser,
    service: WatchlistService,
) -> list[WatchlistItemResponse]:
    """List the instruments tracked by a user's watchlist."""

    try:
        items = await service.list_items(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
        )
    except WatchlistNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found.",
        ) from None

    return [
        WatchlistItemResponse(
            item_id=item.item_id,
            watchlist_id=item.watchlist_id,
            instrument_id=item.instrument_id,
            added_at=item.added_at,
            symbol=item.symbol,
            name=item.name,
            exchange=item.exchange,
            asset_class=item.asset_class,
            currency=item.currency,
            is_active=item.is_active,
        )
        for item in items
    ]


@router.delete(
    "/{watchlist_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_watchlist_item(
    watchlist_id: UUID,
    item_id: UUID,
    current_user: CurrentUser,
    service: WatchlistService,
) -> Response:
    """Remove an instrument from a user's watchlist."""

    try:
        await service.remove_item(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
            item_id=item_id,
        )
    except WatchlistNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found.",
        ) from None
    except WatchlistItemNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist item not found.",
        ) from None

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{watchlist_id}",
    response_model=WatchlistDetailResponse,
)
async def get_watchlist(
    watchlist_id: UUID,
    current_user: CurrentUser,
    service: WatchlistService,
) -> WatchlistDetailResponse:
    """Return an authenticated user's watchlist and its items."""

    try:
        watchlist = await service.get(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
        )
    except WatchlistNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found.",
        ) from None

    return WatchlistDetailResponse(
        watchlist_id=watchlist.watchlist_id,
        name=watchlist.name,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        item_count=watchlist.item_count,
        items=[
            WatchlistItemResponse(
                item_id=item.item_id,
                watchlist_id=item.watchlist_id,
                instrument_id=item.instrument_id,
                added_at=item.added_at,
                symbol=item.symbol,
                name=item.name,
                exchange=item.exchange,
                asset_class=item.asset_class,
                currency=item.currency,
                is_active=item.is_active,
            )
            for item in watchlist.items
        ],
    )


@router.delete(
    "/{watchlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_watchlist(
    watchlist_id: UUID,
    current_user: CurrentUser,
    service: WatchlistService,
) -> Response:
    """Delete an authenticated user's watchlist."""

    try:
        await service.delete(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
        )
    except WatchlistNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found.",
        ) from None

    return Response(status_code=status.HTTP_204_NO_CONTENT)

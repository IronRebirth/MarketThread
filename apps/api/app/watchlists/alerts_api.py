from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.db.session import get_db_session
from app.watchlists.alert_state_persistence import (
    WatchlistAlertStateNotFound,
    WatchlistAlertStatePersistenceService,
    WatchlistAlertStateTransitionError,
)
from app.watchlists.alerts import WatchlistAlertService
from app.watchlists.alerts_schemas import (
    WatchlistAlertResponse,
    WatchlistAlertsResponse,
    WatchlistAlertStateResponse,
    WatchlistAlertStateUpdateRequest,
)

router = APIRouter(
    prefix="/watchlists",
    tags=["watchlist alerts"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get(
    "/{watchlist_id}/alerts",
    response_model=WatchlistAlertsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_watchlist_alerts(
    watchlist_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    limit: int = Query(
        default=100,
        ge=1,
        le=100,
        description="Maximum number of alerts to return.",
    ),
    assessed_at: datetime | None = None,
) -> WatchlistAlertsResponse:
    """Return derived watchlist alerts with durable lifecycle state."""

    service = WatchlistAlertService(session)

    try:
        analysis = await service.build(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
            assessed_at=assessed_at,
            limit=limit,
        )
    except ValueError as exc:
        if str(exc) == "Watchlist not found.":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found.",
            ) from None

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    state_service = WatchlistAlertStatePersistenceService(session)

    try:
        states = await state_service.ensure_for_alerts(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
            alerts=analysis.alerts,
        )
    except WatchlistAlertStateNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found.",
        ) from None

    state_by_alert_id = {state.alert_id: state for state in states}

    responses: list[WatchlistAlertResponse] = []

    for alert in analysis.alerts:
        state = state_by_alert_id.get(alert.alert_id)

        if state is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Alert state could not be resolved.",
            )

        responses.append(
            WatchlistAlertResponse(
                alert_id=alert.alert_id,
                watchlist_id=alert.watchlist_id,
                watchlist_item_id=alert.watchlist_item_id,
                instrument_id=alert.instrument_id,
                symbol=alert.symbol,
                company_name=alert.company_name,
                ticker=alert.ticker,
                market_impact_id=alert.market_impact_id,
                company_impact_id=alert.company_impact_id,
                event_id=alert.event_id,
                event_type=alert.event_type,
                title=alert.title,
                summary=alert.summary,
                catalyst=alert.catalyst,
                market_relevance=alert.market_relevance,
                event_impact_direction=alert.event_impact_direction,
                impact_type=alert.impact_type,
                direction=alert.direction,
                factor=alert.factor,
                time_horizon=alert.time_horizon,
                confidence=alert.confidence,
                event_confidence=alert.event_confidence,
                watchlist_item_added_at=alert.watchlist_item_added_at,
                first_seen_at=alert.first_seen_at,
                last_seen_at=alert.last_seen_at,
                source_article_ids=alert.source_article_ids,
                rationale=alert.rationale,
                explanation=alert.explanation,
                status=state.status,
                seen_at=state.seen_at,
                acknowledged_at=state.acknowledged_at,
            ),
        )

    methodology = (
        f"{analysis.methodology} "
        "Alert lifecycle state is persisted separately from derived "
        "intelligence and is materialized idempotently by stable alert ID."
    )

    return WatchlistAlertsResponse(
        watchlist_id=analysis.watchlist_id,
        assessed_at=analysis.assessed_at,
        item_count=analysis.item_count,
        matched_item_count=analysis.matched_item_count,
        unmatched_item_count=analysis.unmatched_item_count,
        alert_count=analysis.alert_count,
        returned_alert_count=analysis.returned_alert_count,
        quality=analysis.quality,
        alerts=tuple(responses),
        methodology=methodology,
        notes=analysis.notes,
    )


@router.patch(
    "/{watchlist_id}/alerts/{alert_id}/state",
    response_model=WatchlistAlertStateResponse,
    status_code=status.HTTP_200_OK,
)
async def update_watchlist_alert_state(
    watchlist_id: UUID,
    alert_id: UUID,
    payload: WatchlistAlertStateUpdateRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> WatchlistAlertStateResponse:
    """Advance the lifecycle state of an owned watchlist alert."""

    service = WatchlistAlertStatePersistenceService(session)

    try:
        state = await service.update_status(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
            alert_id=alert_id,
            status=payload.status,
        )
    except WatchlistAlertStateNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist alert state not found.",
        ) from None
    except WatchlistAlertStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    return WatchlistAlertStateResponse(
        alert_id=state.alert_id,
        watchlist_id=state.watchlist_id,
        watchlist_item_id=state.watchlist_item_id,
        market_impact_id=state.market_impact_id,
        event_id=state.event_id,
        status=state.status,
        created_at=state.created_at,
        updated_at=state.updated_at,
        seen_at=state.seen_at,
        acknowledged_at=state.acknowledged_at,
    )

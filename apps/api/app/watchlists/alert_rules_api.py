from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.db.session import get_db_session
from app.watchlists.alert_rule_models import AlertRuleType, WatchlistAlertRuleConditions
from app.watchlists.alert_rule_persistence import (
    WatchlistAlertRuleNameConflict,
    WatchlistAlertRuleNotFound,
    WatchlistAlertRulePersistenceService,
)
from app.watchlists.alert_rule_schemas import (
    WatchlistAlertRuleCreateRequest,
    WatchlistAlertRuleResponse,
    WatchlistAlertRuleUpdateRequest,
)

router = APIRouter(
    prefix="/watchlists/{watchlist_id}/alert-rules",
    tags=["watchlist alert rules"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_service(
    session: DatabaseSession,
) -> WatchlistAlertRulePersistenceService:
    return WatchlistAlertRulePersistenceService(session)


AlertRuleServiceDependency = Annotated[
    WatchlistAlertRulePersistenceService,
    Depends(get_service),
]


def _to_response(
    rule,
) -> WatchlistAlertRuleResponse:
    return WatchlistAlertRuleResponse(
        rule_id=str(rule.rule_id),
        watchlist_id=str(rule.watchlist_id),
        name=rule.name,
        rule_type=rule.rule_type,
        conditions=rule.conditions,
        enabled=rule.enabled,
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat(),
    )


@router.post(
    "",
    response_model=WatchlistAlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert_rule(
    watchlist_id: UUID,
    payload: WatchlistAlertRuleCreateRequest,
    current_user: CurrentUser,
    service: AlertRuleServiceDependency,
) -> WatchlistAlertRuleResponse:
    """Create a notification-eligibility rule for an owned watchlist."""

    if payload.rule_type != AlertRuleType.EVENT_IMPACT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported alert rule type.",
        )

    try:
        rule = await service.create(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
            name=payload.name,
            rule_type=payload.rule_type,
            conditions=WatchlistAlertRuleConditions.model_validate(
                payload.conditions.model_dump(),
            ),
            enabled=payload.enabled,
        )
    except WatchlistAlertRuleNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found.",
        ) from None
    except WatchlistAlertRuleNameConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An alert rule with this name already exists.",
        ) from None

    return _to_response(rule)


@router.get(
    "",
    response_model=list[WatchlistAlertRuleResponse],
)
async def list_alert_rules(
    watchlist_id: UUID,
    current_user: CurrentUser,
    service: AlertRuleServiceDependency,
) -> list[WatchlistAlertRuleResponse]:
    """List alert rules for an owned watchlist."""

    try:
        rules = await service.list_for_user(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
        )
    except WatchlistAlertRuleNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found.",
        ) from None

    return [_to_response(rule) for rule in rules]


@router.patch(
    "/{rule_id}",
    response_model=WatchlistAlertRuleResponse,
)
async def update_alert_rule(
    watchlist_id: UUID,
    rule_id: UUID,
    payload: WatchlistAlertRuleUpdateRequest,
    current_user: CurrentUser,
    service: AlertRuleServiceDependency,
) -> WatchlistAlertRuleResponse:
    """Update one owned alert rule."""

    try:
        rule = await service.update(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
            rule_id=rule_id,
            name=payload.name,
            conditions=(
                WatchlistAlertRuleConditions.model_validate(
                    payload.conditions.model_dump(),
                )
                if payload.conditions is not None
                else None
            ),
            enabled=payload.enabled,
        )
    except WatchlistAlertRuleNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found.",
        ) from None
    except WatchlistAlertRuleNameConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An alert rule with this name already exists.",
        ) from None

    return _to_response(rule)


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_alert_rule(
    watchlist_id: UUID,
    rule_id: UUID,
    current_user: CurrentUser,
    service: AlertRuleServiceDependency,
) -> Response:
    """Delete one owned alert rule."""

    try:
        await service.delete(
            user_id=current_user.id,
            watchlist_id=watchlist_id,
            rule_id=rule_id,
        )
    except WatchlistAlertRuleNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found.",
        ) from None

    return Response(status_code=status.HTTP_204_NO_CONTENT)

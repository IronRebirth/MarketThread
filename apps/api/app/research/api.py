from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.db.session import get_db_session
from app.research.models import ResearchContext, ResearchQuery
from app.research.retrieval import ResearchContextService

router = APIRouter(
    prefix="/research",
    tags=["research"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
LimitQuery = Annotated[int, Query(ge=1, le=20)]


@router.post(
    "/context",
    response_model=ResearchContext,
    status_code=status.HTTP_200_OK,
)
async def build_research_context(
    payload: ResearchQuery,
    current_user: CurrentUser,
    session: DatabaseSession,
    limit: LimitQuery = 8,
) -> ResearchContext:
    """Build a timestamp-bounded research context for the authenticated user."""

    query = payload.model_copy(update={"limit": limit})

    try:
        return await ResearchContextService(session).build(
            query,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

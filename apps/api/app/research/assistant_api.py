from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.db.session import get_db_session
from app.research.assistant_models import ResearchAnswer, ResearchAnswerRequest
from app.research.llm import LLMConfigurationError, LLMResponseError
from app.research.service import ResearchAssistantService

router = APIRouter(
    prefix="/research",
    tags=["research"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/answer",
    response_model=ResearchAnswer,
    status_code=status.HTTP_200_OK,
)
async def answer_research_question(
    payload: ResearchAnswerRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ResearchAnswer:
    """Generate a grounded AI answer for the authenticated user."""

    request = payload

    if request.as_of is not None and request.as_of.tzinfo is None:
        request = request.model_copy(
            update={
                "as_of": request.as_of.replace(tzinfo=UTC),
            },
        )

    try:
        return await ResearchAssistantService(session).answer(
            request,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

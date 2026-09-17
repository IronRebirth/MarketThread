from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.news.ingestion import NewsIngestionService
from app.news.intelligence.service import NewsIntelligenceService
from app.news.persistence import (
    NewsArticleNotFoundError,
    NewsPersistenceService,
)
from app.news.providers.errors import (
    NewsProviderError,
    NewsProviderInvalidResponseError,
    NewsProviderUnavailableError,
)
from app.news.providers.factory import create_news_provider
from app.news.schemas import (
    NewsFeedItemResponse,
    to_news_feed_item,
)

router = APIRouter(
    prefix="/news",
    tags=["news"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]

_persistence_service = NewsPersistenceService()
_intelligence_service = NewsIntelligenceService()


def get_news_ingestion_service(
    session: DatabaseSession,
) -> NewsIngestionService:
    """Create the configured news-ingestion service."""

    settings = get_settings()

    try:
        provider = create_news_provider(settings)
    except NewsProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return NewsIngestionService(
        provider=provider,
        persistence=NewsPersistenceService(session),
    )


NewsIngestionDependency = Annotated[
    NewsIngestionService,
    Depends(get_news_ingestion_service),
]


@router.get(
    "",
    response_model=tuple[NewsFeedItemResponse, ...],
    status_code=status.HTTP_200_OK,
    summary="List persisted news",
)
async def list_news(
    session: DatabaseSession,
    query: Annotated[
        str | None,
        Query(
            max_length=500,
            description="Optional text search across persisted titles and summaries.",
        ),
    ] = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
) -> tuple[NewsFeedItemResponse, ...]:
    """Return persisted normalized news with deterministic intelligence."""

    try:
        articles = await _persistence_service.list(
            session,
            query=query,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return tuple(
        to_news_feed_item(
            article,
            _intelligence_service.analyze(article),
        )
        for article in articles
    )


@router.get(
    "/search",
    response_model=tuple[NewsFeedItemResponse, ...],
    status_code=status.HTTP_200_OK,
    summary="Search and persist news",
)
async def search_news(
    query: Annotated[
        str,
        Query(
            min_length=1,
            max_length=500,
        ),
    ],
    session: DatabaseSession,
    ingestion: NewsIngestionDependency,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> tuple[NewsFeedItemResponse, ...]:
    """Search external news, persist snapshots, and analyze the results."""

    try:
        articles = await ingestion.search(
            session,
            query,
            start=start_at,
            end=end_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except NewsProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except NewsProviderInvalidResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except NewsProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return tuple(
        to_news_feed_item(
            article,
            _intelligence_service.analyze(article),
        )
        for article in articles
    )


@router.get(
    "/latest",
    response_model=tuple[NewsFeedItemResponse, ...],
    status_code=status.HTTP_200_OK,
    summary="Retrieve and persist latest news",
)
async def latest_news(
    session: DatabaseSession,
    ingestion: NewsIngestionDependency,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
) -> tuple[NewsFeedItemResponse, ...]:
    """Retrieve recent market-focused news and persist the snapshots."""

    try:
        articles = await ingestion.latest(
            session,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except NewsProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except NewsProviderInvalidResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except NewsProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return tuple(
        to_news_feed_item(
            article,
            _intelligence_service.analyze(article),
        )
        for article in articles
    )


@router.get(
    "/{article_id}",
    response_model=NewsFeedItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a persisted news article",
)
async def get_news_article(
    article_id: UUID,
    session: DatabaseSession,
) -> NewsFeedItemResponse:
    """Return one persisted article with deterministic intelligence."""

    try:
        article = await _persistence_service.get(
            session,
            article_id,
        )
    except NewsArticleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_news_feed_item(
        article,
        _intelligence_service.analyze(article),
    )

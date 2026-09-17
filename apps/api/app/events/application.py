from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.news.intelligence.service import NewsIntelligenceService
from app.news.persistence import NewsPersistenceService

from .models import MarketEvent
from .persistence import EventPersistenceService
from .service import EventIntelligenceService


class EventApplicationService:
    """Coordinate article retrieval, analysis, detection, and persistence."""

    def __init__(
        self,
        news_persistence: NewsPersistenceService | None = None,
        news_intelligence: NewsIntelligenceService | None = None,
        event_intelligence: EventIntelligenceService | None = None,
        event_persistence: EventPersistenceService | None = None,
    ) -> None:
        self._news_persistence = news_persistence or NewsPersistenceService()
        self._news_intelligence = news_intelligence or NewsIntelligenceService()
        self._event_intelligence = event_intelligence or EventIntelligenceService()
        self._event_persistence = event_persistence or EventPersistenceService()

    async def detect_from_article(
        self,
        session: AsyncSession,
        article_id: UUID,
    ) -> MarketEvent:
        article = await self._news_persistence.get(session, article_id)
        intelligence = self._news_intelligence.analyze(article)
        event = self._event_intelligence.detect(article, intelligence)
        return await self._event_persistence.persist(session, event)

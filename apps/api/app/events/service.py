from app.events.detector import EventDetector
from app.events.models import MarketEvent
from app.news.intelligence.models import NewsIntelligence
from app.news.models import NewsArticle


class EventIntelligenceService:
    """Application service for market event intelligence."""

    def __init__(self) -> None:
        self._detector = EventDetector()

    def detect(
        self,
        article: NewsArticle,
        intelligence: NewsIntelligence,
    ) -> MarketEvent:
        """Detect a market event from a news article."""

        return self._detector.detect(
            article=article,
            intelligence=intelligence,
        )

from app.news.intelligence.analyzer import NewsIntelligenceAnalyzer
from app.news.intelligence.models import NewsIntelligence
from app.news.models import NewsArticle


class NewsIntelligenceService:
    """Coordinate deterministic news-intelligence analysis."""

    def __init__(
        self,
        analyzer: NewsIntelligenceAnalyzer | None = None,
    ) -> None:
        self.analyzer = analyzer or NewsIntelligenceAnalyzer()

    def analyze(self, article: NewsArticle) -> NewsIntelligence:
        """Analyze a normalized article."""

        return self.analyzer.analyze(article)

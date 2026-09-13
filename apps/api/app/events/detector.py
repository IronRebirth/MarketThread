import re
from uuid import uuid4

from app.events.models import MarketEvent
from app.events.types import EventCatalyst, EventType
from app.news.intelligence.models import NewsIntelligence
from app.news.models import NewsArticle


def _contains_term(text: str, term: str) -> bool:
    """Check whether text contains a complete word or phrase."""

    return bool(
        re.search(
            rf"(?<!\w){re.escape(term)}(?!\w)",
            text,
        ),
    )


class EventDetector:
    """Detect a normalized market event from news intelligence."""

    def detect(
        self,
        article: NewsArticle,
        intelligence: NewsIntelligence,
    ) -> MarketEvent:
        """Convert article-level intelligence into a market event."""

        text = " ".join(
            value
            for value in (
                article.title,
                article.summary,
            )
            if value
        ).lower()

        event_type, catalyst = self._classify_event(text)

        timestamp = article.published_at or article.discovered_at

        return MarketEvent(
            event_id=uuid4(),
            event_type=event_type,
            title=article.title,
            summary=article.summary or article.title,
            catalyst=catalyst,
            market_relevance=intelligence.market_relevance,
            impact_direction=intelligence.impact_direction,
            affected_entities=intelligence.entities,
            affected_sectors=intelligence.affected_sectors,
            source_article_ids=(article.id,),
            first_seen_at=timestamp,
            last_seen_at=timestamp,
            confidence=intelligence.confidence,
        )

    @staticmethod
    def _classify_event(
        text: str,
    ) -> tuple[EventType, EventCatalyst]:
        """Classify an event from explicit catalyst language."""

        if any(
            _contains_term(text, term)
            for term in (
                "rate cut",
                "cuts interest rates",
            )
        ):
            return EventType.MONETARY_POLICY, EventCatalyst.RATE_CUT

        if any(
            _contains_term(text, term)
            for term in (
                "rate hike",
                "raises interest rates",
            )
        ):
            return EventType.MONETARY_POLICY, EventCatalyst.RATE_HIKE

        if any(
            _contains_term(text, term)
            for term in (
                "interest rate",
                "interest rates",
                "central bank",
            )
        ):
            return EventType.MONETARY_POLICY, EventCatalyst.OTHER

        if _contains_term(text, "inflation"):
            return EventType.INFLATION, EventCatalyst.INFLATION_SURPRISE

        if any(
            _contains_term(text, term)
            for term in (
                "tariff",
                "tariffs",
            )
        ):
            return EventType.TRADE_POLICY, EventCatalyst.TARIFF

        if any(
            _contains_term(text, term)
            for term in (
                "sanction",
                "sanctions",
            )
        ):
            return EventType.GEOPOLITICAL, EventCatalyst.SANCTION

        if any(
            _contains_term(text, term)
            for term in (
                "war",
                "military",
            )
        ):
            return EventType.GEOPOLITICAL, EventCatalyst.MILITARY_ESCALATION

        if _contains_term(text, "merger"):
            return EventType.CORPORATE_ACTION, EventCatalyst.MERGER

        if any(
            _contains_term(text, term)
            for term in (
                "acquisition",
                "acquires",
            )
        ):
            return EventType.CORPORATE_ACTION, EventCatalyst.ACQUISITION

        if _contains_term(text, "earnings"):
            return EventType.EARNINGS, EventCatalyst.EARNINGS_SURPRISE

        if any(
            _contains_term(text, term)
            for term in (
                "regulation",
                "regulatory",
            )
        ):
            return EventType.REGULATION, EventCatalyst.REGULATORY_CHANGE

        return EventType.OTHER, EventCatalyst.OTHER

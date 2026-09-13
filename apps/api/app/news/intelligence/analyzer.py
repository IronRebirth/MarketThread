import re

from app.news.intelligence.entities import (
    extract_entities,
    extract_sectors,
)
from app.news.intelligence.models import (
    ImpactDirection,
    MarketRelevance,
    NewsIntelligence,
    Sentiment,
)
from app.news.models import NewsArticle

POSITIVE_TERMS = frozenset(
    {
        "growth",
        "profit",
        "surge",
        "approval",
        "recovery",
        "expansion",
        "strong",
        "increase",
        "improved",
    }
)

NEGATIVE_TERMS = frozenset(
    {
        "loss",
        "decline",
        "crisis",
        "ban",
        "war",
        "recession",
        "weak",
        "decrease",
        "downgrade",
    }
)

HIGH_RELEVANCE_TERMS = frozenset(
    {
        "interest rate",
        "inflation",
        "sanction",
        "tariff",
        "war",
        "central bank",
        "earnings",
        "regulation",
        "default",
        "merger",
        "acquisition",
    }
)


class NewsIntelligenceAnalyzer:
    """Deterministic baseline analyzer for normalized news."""

    def analyze(self, article: NewsArticle) -> NewsIntelligence:
        """Produce structured intelligence from an article."""

        text = " ".join(
            value
            for value in (
                article.title,
                article.summary,
            )
            if value
        ).lower()

        positive_matches = self._count_matches(text, POSITIVE_TERMS)
        negative_matches = self._count_matches(text, NEGATIVE_TERMS)

        sentiment = self._classify_sentiment(
            positive_matches,
            negative_matches,
        )

        relevance = self._classify_relevance(text)

        impact_direction = self._classify_impact(
            sentiment,
            relevance,
        )

        confidence = self._calculate_confidence(
            positive_matches=positive_matches,
            negative_matches=negative_matches,
            relevance=relevance,
        )

        topics = self._extract_topics(text)
        catalyst = self._detect_catalyst(text)
        entities = extract_entities(text)
        sectors = extract_sectors(text)

        rationale = self._build_rationale(
            sentiment=sentiment,
            relevance=relevance,
            impact_direction=impact_direction,
            catalyst=catalyst,
        )

        return NewsIntelligence(
            article_id=article.id,
            market_relevance=relevance,
            sentiment=sentiment,
            impact_direction=impact_direction,
            confidence=confidence,
            topics=tuple(topics),
            entities=tuple(entity.name for entity in entities),
            affected_sectors=tuple(sector.name for sector in sectors),
            catalyst=catalyst,
            rationale=rationale,
        )

    @staticmethod
    def _count_matches(
        text: str,
        terms: frozenset[str],
    ) -> int:
        """Count complete-word or complete-phrase matches."""

        return sum(
            bool(
                re.search(
                    rf"(?<!\w){re.escape(term)}(?!\w)",
                    text,
                )
            )
            for term in terms
        )

    @staticmethod
    def _classify_sentiment(
        positive_matches: int,
        negative_matches: int,
    ) -> Sentiment:
        """Classify general directional sentiment."""

        if positive_matches > negative_matches:
            return Sentiment.POSITIVE

        if negative_matches > positive_matches:
            return Sentiment.NEGATIVE

        return Sentiment.NEUTRAL

    @staticmethod
    def _classify_relevance(text: str) -> MarketRelevance:
        """Classify market relevance from known catalyst terms."""

        high_relevance_matches = sum(term in text for term in HIGH_RELEVANCE_TERMS)

        if high_relevance_matches >= 2:
            return MarketRelevance.HIGH

        if high_relevance_matches == 1:
            return MarketRelevance.MEDIUM

        return MarketRelevance.LOW

    @staticmethod
    def _classify_impact(
        sentiment: Sentiment,
        relevance: MarketRelevance,
    ) -> ImpactDirection:
        """Translate article interpretation into impact direction."""

        if relevance == MarketRelevance.LOW:
            return ImpactDirection.UNCERTAIN

        if sentiment == Sentiment.POSITIVE:
            return ImpactDirection.POSITIVE

        if sentiment == Sentiment.NEGATIVE:
            return ImpactDirection.NEGATIVE

        return ImpactDirection.NEUTRAL

    @staticmethod
    def _calculate_confidence(
        positive_matches: int,
        negative_matches: int,
        relevance: MarketRelevance,
    ) -> float:
        """Calculate classification confidence."""

        evidence_matches = positive_matches + negative_matches

        base_confidence = min(
            0.55 + (evidence_matches * 0.08),
            0.85,
        )

        if relevance == MarketRelevance.HIGH:
            return min(base_confidence + 0.05, 0.9)

        if relevance == MarketRelevance.LOW:
            return min(base_confidence, 0.65)

        return base_confidence

    @staticmethod
    def _extract_topics(text: str) -> list[str]:
        """Extract a small deterministic topic vocabulary."""

        topic_terms = {
            "inflation": "inflation",
            "interest rate": "monetary policy",
            "earnings": "earnings",
            "tariff": "trade policy",
            "sanction": "geopolitics",
            "war": "geopolitics",
            "regulation": "regulation",
            "merger": "M&A",
            "acquisition": "M&A",
        }

        return sorted({topic for term, topic in topic_terms.items() if term in text})

    @staticmethod
    def _detect_catalyst(text: str) -> str | None:
        """Detect the primary catalyst category."""

        catalyst_terms = (
            ("monetary_policy", ("interest rate", "central bank")),
            ("inflation", ("inflation",)),
            ("trade_policy", ("tariff",)),
            ("geopolitical", ("sanction", "war")),
            ("corporate_action", ("merger", "acquisition")),
            ("earnings", ("earnings",)),
            ("regulation", ("regulation",)),
        )

        for catalyst, terms in catalyst_terms:
            if any(term in text for term in terms):
                return catalyst

        return None

    @staticmethod
    def _build_rationale(
        sentiment: Sentiment,
        relevance: MarketRelevance,
        impact_direction: ImpactDirection,
        catalyst: str | None,
    ) -> str:
        """Build a concise explanation of the classification."""

        catalyst_text = catalyst or "no specific catalyst detected"

        return (
            f"Classified as {relevance.value} market relevance with "
            f"{sentiment.value} sentiment and {impact_direction.value} "
            f"potential impact; {catalyst_text}."
        )

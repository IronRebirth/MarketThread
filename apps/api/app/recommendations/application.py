from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.market_impact.persistence import MarketImpactPersistenceService
from app.risk.service import RiskConfidenceService
from app.signals.models import (
    MarketSignal,
    SignalDirection,
    SignalOpportunity,
    SignalStrength,
)
from app.signals.persistence import SignalPersistenceService

from .persistence import RecommendationPersistenceService
from .service import RecommendationIntelligenceService


class RecommendationMarketImpactRequiredError(Exception):
    """Raised when a persisted signal is not linked to a market impact."""


class RecommendationDataConsistencyError(Exception):
    """Raised when linked intelligence records are inconsistent."""


class RecommendationApplicationService:
    """Coordinate persisted signals, risk assessment, and recommendations."""

    def __init__(
        self,
        signal_persistence: SignalPersistenceService | None = None,
        market_impact_persistence: MarketImpactPersistenceService | None = None,
        risk_confidence_service: RiskConfidenceService | None = None,
        recommendation_service: RecommendationIntelligenceService | None = None,
        recommendation_persistence: RecommendationPersistenceService | None = None,
    ) -> None:
        self._signal_persistence = signal_persistence or SignalPersistenceService()
        self._market_impact_persistence = (
            market_impact_persistence or MarketImpactPersistenceService()
        )
        self._risk_confidence_service = (
            risk_confidence_service or RiskConfidenceService()
        )
        self._recommendation_service = (
            recommendation_service or RecommendationIntelligenceService()
        )
        self._recommendation_persistence = (
            recommendation_persistence or RecommendationPersistenceService()
        )

    async def generate_from_signal(
        self,
        session: AsyncSession,
        signal_id: UUID,
    ):
        """Generate or retrieve the recommendation for a persisted signal."""

        existing = await self._recommendation_persistence.get_by_signal_id(
            session,
            signal_id,
        )

        if existing is not None:
            return existing

        signal_record = await self._signal_persistence.get(
            session,
            signal_id,
        )

        if signal_record.market_impact_id is None:
            raise RecommendationMarketImpactRequiredError(
                "Recommendation generation requires the signal to be linked "
                "to a persisted market impact.",
            )

        market_impact = await self._market_impact_persistence.get(
            session,
            signal_record.market_impact_id,
        )

        if market_impact.event_id != signal_record.event_id:
            raise RecommendationDataConsistencyError(
                "Signal and market impact event identifiers do not match.",
            )

        signal = self._to_domain_signal(signal_record)

        risk_confidence = self._risk_confidence_service.analyze(
            signal,
            market_impact,
        )

        recommendation = self._recommendation_service.analyze(
            signal,
            risk_confidence,
        )

        return await self._recommendation_persistence.create(
            session,
            recommendation=recommendation,
            signal_id=signal_id,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _to_domain_signal(signal_record) -> MarketSignal:
        """Convert a persisted signal snapshot into a domain signal."""

        return MarketSignal(
            event_id=signal_record.event_id,
            company_name=signal_record.company_name,
            ticker=signal_record.ticker,
            direction=SignalDirection(signal_record.direction),
            strength=SignalStrength(signal_record.strength),
            opportunity=SignalOpportunity(signal_record.opportunity),
            confidence=signal_record.confidence,
            risk_score=signal_record.risk_score,
            time_horizon=signal_record.time_horizon,
            supporting_factors=tuple(signal_record.supporting_factors),
            contradicting_factors=tuple(
                signal_record.contradicting_factors,
            ),
            evidence_article_ids=tuple(
                UUID(article_id) for article_id in signal_record.evidence_article_ids
            ),
            invalidation_conditions=tuple(
                signal_record.invalidation_conditions,
            ),
            rationale=signal_record.rationale,
        )

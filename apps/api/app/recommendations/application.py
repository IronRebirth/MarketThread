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
from .provenance import RecommendationProvenance
from .provenance_persistence import (
    RecommendationProvenancePersistenceService,
)
from .service import RecommendationIntelligenceService


class RecommendationMarketImpactRequiredError(Exception):
    """Raised when a persisted signal is not linked to a market impact."""


class RecommendationDataConsistencyError(Exception):
    """Raised when linked intelligence records are inconsistent."""


class RecommendationApplicationService:
    """Coordinate persisted signals, risk, recommendations, and provenance."""

    def __init__(
        self,
        signal_persistence: SignalPersistenceService | None = None,
        market_impact_persistence: MarketImpactPersistenceService | None = None,
        risk_confidence_service: RiskConfidenceService | None = None,
        recommendation_service: RecommendationIntelligenceService | None = None,
        recommendation_persistence: RecommendationPersistenceService | None = None,
        provenance_persistence: (
            RecommendationProvenancePersistenceService | None
        ) = None,
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
        self._provenance_persistence = (
            provenance_persistence or RecommendationProvenancePersistenceService()
        )

    async def generate_from_signal(
        self,
        session: AsyncSession,
        signal_id: UUID,
    ):
        """Generate or retrieve a recommendation and its provenance."""

        existing = await self._recommendation_persistence.get_by_signal_id(
            session,
            signal_id,
        )

        if existing is not None:
            await self._ensure_provenance(
                session,
                existing,
            )
            return existing

        signal_record = await self._signal_persistence.get(
            session,
            signal_id,
        )

        market_impact = await self._get_market_impact(
            session,
            signal_record,
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

        record = await self._recommendation_persistence.create(
            session,
            recommendation=recommendation,
            signal_id=signal_id,
            created_at=datetime.now(UTC),
        )

        await self._create_provenance(
            session,
            record,
            signal_record,
        )

        return record

    async def get_provenance(
        self,
        session: AsyncSession,
        recommendation_id: UUID,
    ):
        """Retrieve the provenance associated with a recommendation."""

        recommendation = await self._recommendation_persistence.get(
            session,
            recommendation_id,
        )

        provenance = await self._provenance_persistence.get_by_recommendation_id(
            session,
            recommendation.id,
        )

        if provenance is None:
            signal_record = await self._signal_persistence.get(
                session,
                recommendation.signal_id,
            )
            await self._get_market_impact(
                session,
                signal_record,
            )
            provenance = await self._create_provenance(
                session,
                recommendation,
                signal_record,
            )

        return self._provenance_persistence.to_domain(provenance)

    async def _ensure_provenance(
        self,
        session: AsyncSession,
        recommendation_record,
    ):
        """Create missing provenance for an existing recommendation."""

        existing = await self._provenance_persistence.get_by_recommendation_id(
            session,
            recommendation_record.id,
        )

        if existing is not None:
            return existing

        signal_record = await self._signal_persistence.get(
            session,
            recommendation_record.signal_id,
        )

        await self._get_market_impact(
            session,
            signal_record,
        )

        return await self._create_provenance(
            session,
            recommendation_record,
            signal_record,
        )

    async def _create_provenance(
        self,
        session: AsyncSession,
        recommendation_record,
        signal_record,
    ):
        """Create provenance from persisted recommendation inputs."""

        if signal_record.market_impact_id is None:
            raise RecommendationMarketImpactRequiredError(
                "Recommendation provenance requires the signal to be linked "
                "to a persisted market impact.",
            )

        provenance = RecommendationProvenance(
            recommendation_id=recommendation_record.id,
            signal_id=signal_record.id,
            market_impact_id=signal_record.market_impact_id,
            event_id=recommendation_record.event_id,
            created_at=recommendation_record.created_at,
            ruleset_version="1.0.0",
            input_ids=(
                signal_record.id,
                signal_record.market_impact_id,
                recommendation_record.event_id,
            ),
            evidence_article_ids=tuple(
                UUID(article_id)
                for article_id in recommendation_record.evidence_article_ids
            ),
            assumptions=tuple(recommendation_record.assumptions),
            invalidation_conditions=tuple(
                recommendation_record.invalidation_conditions,
            ),
        )

        return await self._provenance_persistence.create(
            session,
            provenance=provenance,
            created_at=recommendation_record.created_at,
        )

    async def _get_market_impact(
        self,
        session: AsyncSession,
        signal_record,
    ):
        """Resolve and validate the market impact linked to a signal."""

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

        return market_impact

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

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_impact.persistence import CompanyImpactPersistenceService
from app.db.models.company_impact import CompanyImpactRecord
from app.events.persistence import EventPersistenceService

from .models import MarketImpact
from .persistence import MarketImpactPersistenceService
from .service import MarketImpactService


class MarketImpactApplicationService:
    """Coordinate event, company-impact, analysis, and persistence."""

    def __init__(
        self,
        event_persistence: EventPersistenceService | None = None,
        company_impact_persistence: CompanyImpactPersistenceService | None = None,
        market_impact_service: MarketImpactService | None = None,
        market_impact_persistence: MarketImpactPersistenceService | None = None,
    ) -> None:
        self._event_persistence = event_persistence or EventPersistenceService()
        self._company_impact_persistence = (
            company_impact_persistence or CompanyImpactPersistenceService()
        )
        self._market_impact_service = market_impact_service or MarketImpactService()
        self._market_impact_persistence = (
            market_impact_persistence or MarketImpactPersistenceService()
        )

    async def analyze_from_event(
        self,
        session: AsyncSession,
        event_id: UUID,
    ) -> tuple[tuple[UUID, MarketImpact], ...]:
        """Analyze and persist market impacts for all company impacts."""

        event = await self._event_persistence.get(
            session,
            event_id,
        )

        company_impact_ids = (
            await session.execute(
                select(
                    CompanyImpactRecord.id,
                    CompanyImpactRecord.event_id,
                ).where(
                    CompanyImpactRecord.event_id == event.event_id,
                ),
            )
        ).all()

        results: list[tuple[UUID, MarketImpact]] = []

        for company_impact_id, _ in company_impact_ids:
            company_impact = await self._company_impact_persistence.get(
                session,
                company_impact_id,
            )

            market_impact = self._market_impact_service.analyze(
                event,
                company_impact,
            )

            persisted = await self._market_impact_persistence.persist(
                session,
                market_impact,
                company_impact_id,
            )

            results.append(
                (
                    company_impact_id,
                    persisted,
                ),
            )

        return tuple(results)

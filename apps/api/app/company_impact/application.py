from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.events.persistence import EventPersistenceService

from .models import CompanyImpact
from .persistence import CompanyImpactPersistenceService
from .service import CompanyImpactService


class CompanyImpactApplicationService:
    """Coordinate event retrieval, company analysis, and persistence."""

    def __init__(
        self,
        event_persistence: EventPersistenceService | None = None,
        company_impact_service: CompanyImpactService | None = None,
        company_impact_persistence: CompanyImpactPersistenceService | None = None,
    ) -> None:
        self._event_persistence = event_persistence or EventPersistenceService()
        self._company_impact_service = company_impact_service or CompanyImpactService()
        self._company_impact_persistence = (
            company_impact_persistence or CompanyImpactPersistenceService()
        )

    async def analyze_from_event(
        self,
        session: AsyncSession,
        event_id: UUID,
    ) -> tuple[CompanyImpact, ...]:
        """Analyze and persist company impacts for one market event."""

        event = await self._event_persistence.get(
            session,
            event_id,
        )

        impacts = self._company_impact_service.analyze(event)

        return await self._company_impact_persistence.persist_many(
            session,
            impacts,
        )

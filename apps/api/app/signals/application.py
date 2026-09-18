from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.market_data.repository import MarketDataRepository
from app.market_impact.persistence import MarketImpactPersistenceService

from .persistence import SignalPersistenceService
from .service import SignalIntelligenceService


class SignalInstrumentResolutionError(Exception):
    """Raised when a signal cannot be mapped to a persisted instrument."""


class SignalInstrumentNotFoundError(SignalInstrumentResolutionError):
    """Raised when no active persisted instrument matches the ticker."""


class SignalApplicationService:
    """Coordinate market-impact retrieval, instrument resolution, and signals."""

    def __init__(
        self,
        market_impact_persistence: MarketImpactPersistenceService | None = None,
        signal_service: SignalIntelligenceService | None = None,
        signal_persistence: SignalPersistenceService | None = None,
    ) -> None:
        self._market_impact_persistence = (
            market_impact_persistence or MarketImpactPersistenceService()
        )
        self._signal_service = signal_service or SignalIntelligenceService()
        self._signal_persistence = signal_persistence or SignalPersistenceService()

    async def generate_from_market_impact(
        self,
        session: AsyncSession,
        market_impact_id: UUID,
    ):
        """Generate or retrieve the signal for a persisted market impact."""

        market_impact = await self._market_impact_persistence.get(
            session,
            market_impact_id,
        )

        ticker = (market_impact.ticker or "").strip().upper()

        if not ticker:
            raise SignalInstrumentResolutionError(
                "Signal generation requires a ticker on the market impact.",
            )

        instrument = await MarketDataRepository(session).get_instrument(
            ticker,
        )

        if instrument is None:
            raise SignalInstrumentNotFoundError(
                f"No active persisted instrument was found for ticker {ticker}.",
            )

        signal = self._signal_service.analyze(
            market_impact,
        )

        return await self._signal_persistence.create(
            session,
            signal=signal,
            instrument_id=instrument.id,
            created_at=datetime.now(UTC),
            market_impact_id=market_impact_id,
        )

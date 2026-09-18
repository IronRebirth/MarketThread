from datetime import datetime
from uuid import UUID

from app.db.models.instrument import Instrument
from app.portfolio.history_models import (
    PortfolioHistoricalPosition,
    PortfolioHistoricalState,
)
from app.portfolio.models import Portfolio
from app.portfolio.persistence import PortfolioPersistenceService


class PortfolioHistoricalStateService:
    """Reconstruct portfolio positions at a historical point in time."""

    def __init__(
        self,
        persistence: PortfolioPersistenceService,
    ) -> None:
        self.persistence = persistence

    async def build(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        as_of: datetime,
    ) -> PortfolioHistoricalState:
        """Build the position state that existed at ``as_of``."""

        self._validate_aware_datetime(
            as_of,
            "as_of",
        )

        detail = await self.persistence.get_for_user(
            user_id,
            portfolio_id,
        )

        if detail is None:
            raise ValueError("Portfolio not found.")

        portfolio_record, _current_position_count = detail

        history_records = await self.persistence.list_position_history_at(
            user_id,
            portfolio_id,
            as_of,
        )

        positions: list[PortfolioHistoricalPosition] = []

        for history_record in history_records:
            if history_record.quantity <= 0:
                continue

            instrument = await self.persistence.session.get(
                Instrument,
                history_record.instrument_id,
            )

            if instrument is None:
                raise RuntimeError(
                    "Historical portfolio position references a missing instrument.",
                )

            positions.append(
                PortfolioHistoricalPosition(
                    history_sequence_id=history_record.sequence_id,
                    portfolio_id=history_record.portfolio_id,
                    instrument_id=history_record.instrument_id,
                    quantity=history_record.quantity,
                    average_cost=history_record.average_cost,
                    event_type=history_record.event_type,
                    effective_at=history_record.recorded_at,
                    symbol=instrument.symbol,
                    name=instrument.name,
                    exchange=instrument.exchange,
                    asset_class=instrument.asset_class,
                    currency=instrument.currency,
                    is_active=instrument.is_active,
                ),
            )

        positions_tuple = tuple(positions)

        portfolio = Portfolio(
            portfolio_id=portfolio_record.id,
            name=portfolio_record.name,
            created_at=portfolio_record.created_at,
            updated_at=portfolio_record.updated_at,
            position_count=len(positions_tuple),
        )

        return PortfolioHistoricalState(
            portfolio=portfolio,
            as_of=as_of,
            position_count=len(positions_tuple),
            quality="complete" if positions_tuple else "empty",
            methodology=self._methodology(),
            positions=positions_tuple,
        )

    @staticmethod
    def _validate_aware_datetime(
        value: datetime,
        label: str,
    ) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware")

    @staticmethod
    def _methodology() -> str:
        """Describe the historical state reconstruction methodology."""

        return (
            "Historical state is reconstructed from the latest recorded position "
            "event for each instrument at or before the requested timestamp. "
            "Zero-quantity deletion states are excluded from active holdings."
        )

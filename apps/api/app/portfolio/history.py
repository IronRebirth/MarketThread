from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.db.models.instrument import Instrument
from app.portfolio.history_models import (
    PortfolioHistoricalPosition,
    PortfolioHistoricalState,
)
from app.portfolio.models import Portfolio
from app.portfolio.persistence import PortfolioPersistenceService


class PortfolioHistoricalStateService:
    """Reconstruct portfolio positions at historical points in time."""

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

        states = await self.build_many(
            user_id,
            portfolio_id,
            as_ofs=(as_of,),
        )

        return states[0]

    async def build_many(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        as_ofs: Sequence[datetime],
    ) -> tuple[PortfolioHistoricalState, ...]:
        """Build historical states for multiple timestamps efficiently."""

        if not as_ofs:
            return ()

        normalized_as_ofs = tuple(
            sorted(
                {
                    self._normalize_aware_datetime(
                        value,
                        "as_of",
                    )
                    for value in as_ofs
                },
            ),
        )

        detail = await self.persistence.get_for_user(
            user_id,
            portfolio_id,
        )

        if detail is None:
            raise ValueError("Portfolio not found.")

        portfolio_record, _current_position_count = detail

        history_records = await self.persistence.list_position_history_for_window(
            user_id=user_id,
            portfolio_id=portfolio_id,
            start_at=normalized_as_ofs[0],
            end_at=normalized_as_ofs[-1],
        )

        instrument_ids = {
            history_record.instrument_id for history_record in history_records
        }

        instruments: dict[UUID, Instrument] = {}

        for instrument_id in instrument_ids:
            instrument = await self.persistence.session.get(
                Instrument,
                instrument_id,
            )

            if instrument is None:
                raise RuntimeError(
                    "Historical portfolio position references a missing instrument.",
                )

            instruments[instrument_id] = instrument

        ordered_history = tuple(
            sorted(
                history_records,
                key=lambda history_record: (
                    self._normalize_aware_datetime(
                        history_record.recorded_at,
                        "recorded_at",
                    ),
                    history_record.sequence_id,
                ),
            )
        )

        current_state = {}
        history_index = 0
        results: list[PortfolioHistoricalState] = []

        for as_of in normalized_as_ofs:
            while history_index < len(ordered_history):
                history_record = ordered_history[history_index]

                recorded_at = self._normalize_aware_datetime(
                    history_record.recorded_at,
                    "recorded_at",
                )

                if recorded_at > as_of:
                    break

                current_state[history_record.instrument_id] = history_record
                history_index += 1

            positions: list[PortfolioHistoricalPosition] = []

            for instrument_id in sorted(current_state, key=str):
                history_record = current_state[instrument_id]

                if history_record.quantity <= 0:
                    continue

                instrument = instruments[instrument_id]

                positions.append(
                    PortfolioHistoricalPosition(
                        history_sequence_id=history_record.sequence_id,
                        portfolio_id=history_record.portfolio_id,
                        instrument_id=history_record.instrument_id,
                        quantity=history_record.quantity,
                        average_cost=history_record.average_cost,
                        event_type=history_record.event_type,
                        effective_at=self._normalize_aware_datetime(
                            history_record.recorded_at,
                            "recorded_at",
                        ),
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

            results.append(
                PortfolioHistoricalState(
                    portfolio=portfolio,
                    as_of=as_of,
                    position_count=len(positions_tuple),
                    quality="complete" if positions_tuple else "empty",
                    methodology=self._methodology(),
                    positions=positions_tuple,
                ),
            )

        return tuple(results)

    @staticmethod
    def _normalize_aware_datetime(
        value: datetime,
        label: str,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware")

        return value.astimezone(UTC)

    @staticmethod
    def _methodology() -> str:
        """Describe the historical state reconstruction methodology."""

        return (
            "Historical state is reconstructed from the latest recorded position "
            "event for each instrument at or before the requested timestamp. "
            "Zero-quantity deletion states are excluded from active holdings."
        )

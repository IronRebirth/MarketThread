from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from app.db.models.instrument import Instrument
from app.market_data.models import Bar
from app.market_data.providers.errors import MarketDataProviderError
from app.market_data.service import MarketDataService
from app.portfolio.cash_flow_persistence import (
    PortfolioCashFlowPersistenceService,
)
from app.portfolio.history import PortfolioHistoricalStateService
from app.portfolio.history_models import PortfolioHistoricalPosition
from app.portfolio.models import Portfolio
from app.portfolio.performance_models import (
    PerformanceQuality,
    PortfolioCurrencyPerformance,
    PortfolioPerformance,
    PortfolioPerformancePoint,
)
from app.portfolio.persistence import PortfolioPersistenceService


class PortfolioPerformanceService:
    """Build time-aware historical portfolio value and return series."""

    def __init__(
        self,
        persistence: PortfolioPersistenceService,
        market_data: MarketDataService,
        cash_flow_persistence: PortfolioCashFlowPersistenceService | None = None,
    ) -> None:
        self.persistence = persistence
        self.market_data = market_data
        self.cash_flow_persistence = cash_flow_persistence
        self.historical_state = PortfolioHistoricalStateService(
            persistence,
        )

    async def build(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        assessed_at: datetime | None = None,
        lookback_days: int = 365,
    ) -> PortfolioPerformance:
        """Build currency-separated historical performance from position history."""

        if lookback_days <= 0:
            raise ValueError("lookback_days must be greater than zero")

        assessment_time = assessed_at or datetime.now(UTC)

        self._validate_aware_datetime(
            assessment_time,
            "assessed_at",
        )

        assessment_time = assessment_time.astimezone(UTC)
        lookback_start = assessment_time - timedelta(days=lookback_days)

        detail = await self.persistence.get_for_user(
            user_id,
            portfolio_id,
        )

        if detail is None:
            raise ValueError("Portfolio not found.")

        portfolio_record, current_position_count = detail

        portfolio = Portfolio(
            portfolio_id=portfolio_record.id,
            name=portfolio_record.name,
            created_at=portfolio_record.created_at,
            updated_at=portfolio_record.updated_at,
            position_count=current_position_count,
        )

        historical_instrument_ids = await self._list_historical_instrument_ids(
            user_id=user_id,
            portfolio_id=portfolio_id,
            end_at=assessment_time,
        )

        if not historical_instrument_ids:
            return PortfolioPerformance(
                portfolio=portfolio,
                assessed_at=assessment_time,
                lookback_start=lookback_start,
                lookback_end=assessment_time,
                lookback_days=lookback_days,
                position_count=current_position_count,
                quality="empty",
                methodology=self._methodology(),
                currencies=(),
            )

        instruments = await self._build_instruments(
            historical_instrument_ids,
        )

        position_histories = await self._load_market_histories(
            historical_instrument_ids=historical_instrument_ids,
            start_at=lookback_start,
            end_at=assessment_time,
        )

        candidate_days = self._candidate_days(
            position_histories,
        )

        if not candidate_days:
            return self._unavailable_result(
                portfolio=portfolio,
                assessment_time=assessment_time,
                lookback_start=lookback_start,
                lookback_days=lookback_days,
                position_histories=position_histories,
                instruments=instruments,
            )

        observation_times = tuple(
            self._utc_day_end(observed_on) for observed_on in candidate_days
        )

        historical_states = await self.historical_state.build_many(
            user_id,
            portfolio_id,
            as_ofs=observation_times,
        )

        state_by_day = {state.as_of.date(): state for state in historical_states}

        cash_flows_by_currency = await self._load_cash_flows(
            user_id=user_id,
            portfolio_id=portfolio_id,
            start_at=lookback_start,
            end_at=assessment_time,
        )

        currencies = self._historical_currencies(
            historical_states,
        )

        currency_results: list[PortfolioCurrencyPerformance] = []

        for currency in sorted(currencies):
            result = self._build_currency_performance(
                currency=currency,
                historical_states=historical_states,
                state_by_day=state_by_day,
                position_histories=position_histories,
                instruments=instruments,
                candidate_days=candidate_days,
                start_at=lookback_start,
                end_at=assessment_time,
                cash_flows=cash_flows_by_currency.get(currency, ()),
            )
            currency_results.append(result)

        currency_results_tuple = tuple(currency_results)

        return PortfolioPerformance(
            portfolio=portfolio,
            assessed_at=assessment_time,
            lookback_start=lookback_start,
            lookback_end=assessment_time,
            lookback_days=lookback_days,
            position_count=current_position_count,
            quality=self._aggregate_quality(
                currency_results_tuple,
            ),
            methodology=self._methodology(),
            currencies=currency_results_tuple,
        )

    async def _load_cash_flows(
        self,
        *,
        user_id: UUID,
        portfolio_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> dict[str, tuple]:
        """Load external cash flows for the performance window."""

        if self.cash_flow_persistence is None:
            return {}

        records = await self.cash_flow_persistence.list_for_user(
            user_id,
            portfolio_id,
            start_at=start_at,
            end_at=end_at,
            limit=None,
        )

        grouped: dict[str, list] = {}

        for record in records:
            grouped.setdefault(record.currency, []).append(record)

        return {currency: tuple(events) for currency, events in grouped.items()}

    async def _list_historical_instrument_ids(
        self,
        *,
        user_id: UUID,
        portfolio_id: UUID,
        end_at: datetime,
    ) -> tuple[UUID, ...]:
        result = await self.persistence.session.execute(
            self._historical_instrument_ids_statement(
                user_id=user_id,
                portfolio_id=portfolio_id,
                end_at=end_at,
            ),
        )

        return tuple(result.scalars().all())

    @staticmethod
    def _historical_instrument_ids_statement(
        *,
        user_id: UUID,
        portfolio_id: UUID,
        end_at: datetime,
    ):
        from sqlalchemy import distinct, select

        from app.db.models.portfolio import PortfolioRecord
        from app.db.models.portfolio_history import (
            PortfolioPositionHistoryRecord,
        )

        return (
            select(
                distinct(
                    PortfolioPositionHistoryRecord.instrument_id,
                ),
            )
            .join(
                PortfolioRecord,
                PortfolioRecord.id == PortfolioPositionHistoryRecord.portfolio_id,
            )
            .where(
                PortfolioPositionHistoryRecord.portfolio_id == portfolio_id,
                PortfolioRecord.user_id == user_id,
                PortfolioPositionHistoryRecord.recorded_at <= end_at,
            )
            .order_by(
                PortfolioPositionHistoryRecord.instrument_id,
            )
        )

    async def _build_instruments(
        self,
        instrument_ids: Sequence[UUID],
    ) -> dict[UUID, Instrument]:
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

        return instruments

    async def _load_market_histories(
        self,
        *,
        historical_instrument_ids: Sequence[UUID],
        start_at: datetime,
        end_at: datetime,
    ) -> dict[
        UUID,
        tuple[
            dict[date, tuple[datetime, Decimal]],
            set[str],
        ],
    ]:
        histories: dict[
            UUID,
            tuple[
                dict[date, tuple[datetime, Decimal]],
                set[str],
            ],
        ] = {}

        for instrument_id in historical_instrument_ids:
            try:
                bars = await self.market_data.get_historical_bars(
                    instrument_id,
                    start_at,
                    end_at,
                )
            except MarketDataProviderError:
                bars = ()

            histories[instrument_id] = self._select_daily_closes(
                bars,
            )

        return histories

    @staticmethod
    def _candidate_days(
        position_histories: dict[
            UUID,
            tuple[
                dict[date, tuple[datetime, Decimal]],
                set[str],
            ],
        ],
    ) -> tuple[date, ...]:
        observed_days: set[date] = set()

        for daily_bars, _sources in position_histories.values():
            observed_days.update(daily_bars)

        return tuple(sorted(observed_days))

    @staticmethod
    def _historical_currencies(
        historical_states,
    ) -> set[str]:
        currencies: set[str] = set()

        for state in historical_states:
            for position in state.positions:
                currencies.add(position.currency)

        return currencies

    def _build_currency_performance(
        self,
        *,
        currency: str,
        historical_states,
        state_by_day,
        position_histories: dict[
            UUID,
            tuple[
                dict[date, tuple[datetime, Decimal]],
                set[str],
            ],
        ],
        instruments: dict[UUID, Instrument],
        candidate_days: Sequence[date],
        start_at: datetime,
        end_at: datetime,
        cash_flows: Sequence,
    ) -> PortfolioCurrencyPerformance:
        historical_instrument_ids = {
            position.instrument_id
            for state in historical_states
            for position in state.positions
            if position.currency == currency
        }

        active_days = 0
        complete_active_days = 0
        missing_symbols: set[str] = set()

        points: list[PortfolioPerformancePoint] = []

        for observed_day in candidate_days:
            state = state_by_day[observed_day]

            active_positions = tuple(
                position
                for position in state.positions
                if position.currency == currency
            )

            if not active_positions:
                if historical_instrument_ids:
                    points.append(
                        PortfolioPerformancePoint(
                            observed_on=observed_day,
                            value=Decimal("0"),
                        ),
                    )
                continue

            active_days += 1

            missing_position = False

            for position in active_positions:
                daily_bars, _sources = position_histories[position.instrument_id]

                if observed_day not in daily_bars:
                    missing_symbols.add(
                        position.symbol,
                    )
                    missing_position = True

            if missing_position:
                continue

            complete_active_days += 1

            portfolio_value = Decimal("0")

            for position in active_positions:
                daily_bars, _sources = position_histories[position.instrument_id]
                _, close = daily_bars[observed_day]

                portfolio_value += position.quantity * close

            points.append(
                PortfolioPerformancePoint(
                    observed_on=observed_day,
                    value=portfolio_value,
                ),
            )

        sources = tuple(
            sorted(
                {
                    source
                    for instrument_id in historical_instrument_ids
                    for source in position_histories[instrument_id][1]
                },
            ),
        )

        if not points:
            notes = [
                (
                    "No historical portfolio state had a corresponding "
                    "market-data observation."
                ),
            ]

            if missing_symbols:
                notes.append(
                    "Historical bars were unavailable for: "
                    + ", ".join(sorted(missing_symbols))
                    + ".",
                )

            return PortfolioCurrencyPerformance(
                currency=currency,
                position_count=len(historical_instrument_ids),
                quality="unavailable",
                first_observed_on=None,
                last_observed_on=None,
                observation_count=0,
                return_count=0,
                initial_value=None,
                latest_value=None,
                period_return=None,
                external_cash_flow_adjusted_period_return=None,
                external_cash_flow_count=0,
                external_net_cash_flow=Decimal("0"),
                points=(),
                sources=sources,
                notes=tuple(notes),
            )

        initial_value = points[0].value
        latest_value = points[-1].value

        first_observed_on = points[0].observed_on
        last_observed_on = points[-1].observed_on

        period_return: Decimal | None = None

        state_changed_after_first_observation = (
            self._has_position_change_after_first_observation(
                currency=currency,
                first_observed_on=first_observed_on,
                last_observed_on=last_observed_on,
                historical_states=historical_states,
            )
        )

        qualifying_cash_flows = self._qualifying_cash_flows(
            currency=currency,
            first_observed_on=first_observed_on,
            last_observed_on=last_observed_on,
            cash_flows=cash_flows,
        )

        external_cash_flow_count = len(qualifying_cash_flows)
        external_net_cash_flow = self._net_external_cash_flow(
            qualifying_cash_flows,
        )

        notes = [
            (
                "Historical holdings are reconstructed from position history "
                "at each UTC day-end."
            ),
            "Position changes are reflected directly in the historical value series.",
            "No synthetic prices are created for missing historical observations.",
            (
                "Portfolio values are calculated separately for each currency; "
                "no FX conversion is performed."
            ),
        ]

        if missing_symbols:
            notes.append(
                "Historical bars were unavailable for: "
                + ", ".join(sorted(missing_symbols))
                + ".",
            )

        if complete_active_days < active_days:
            notes.append(
                (
                    "Only dates with historical closes for every active position "
                    "in the currency were included."
                ),
            )

        if initial_value > 0 and len(points) >= 2:
            if state_changed_after_first_observation:
                notes.append(
                    (
                        "Simple period return is withheld because holdings changed "
                        "after the first complete observation."
                    ),
                )
            else:
                period_return = (latest_value / initial_value) - Decimal("1")

        external_cash_flow_adjusted_period_return = (
            self._build_external_cash_flow_adjusted_return(
                initial_value=initial_value,
                latest_value=latest_value,
                point_count=len(points),
                state_changed_after_first_observation=(
                    state_changed_after_first_observation
                ),
                period_return=period_return,
                external_net_cash_flow=external_net_cash_flow,
                external_cash_flow_count=external_cash_flow_count,
            )
        )

        if external_cash_flow_count:
            notes.append(
                (
                    f"{external_cash_flow_count} recorded external cash-flow event(s) "
                    "fell after the first complete observation and on or before "
                    "the last complete observation."
                ),
            )

        if state_changed_after_first_observation and external_cash_flow_count:
            notes.append(
                (
                    "External cash-flow-adjusted return is a proxy that assumes "
                    "the net recorded external flow explains the corresponding "
                    "change in invested portfolio value. Trade-level purchases, "
                    "sales, dividends, and internal cash movements are not modeled."
                ),
            )
        elif not state_changed_after_first_observation and external_cash_flow_count:
            notes.append(
                (
                    "External cash flows did not coincide with a recorded holding "
                    "change, so the invested-value period return remains unchanged."
                ),
            )
        elif state_changed_after_first_observation:
            notes.append(
                (
                    "No qualifying external cash flow was available to provide a "
                    "cash-flow adjustment for the holding change."
                ),
            )

        if len(points) < 2:
            quality: PerformanceQuality = "insufficient"
            notes.append(
                "At least two complete observations are required to calculate "
                "period return.",
            )
        elif state_changed_after_first_observation or initial_value <= 0:
            quality = "insufficient"

            if initial_value <= 0:
                notes.append(
                    (
                        "Period return is unavailable because the first observed "
                        "portfolio value is zero."
                    ),
                )
        else:
            quality = "sufficient"

        if complete_active_days == 0 and active_days > 0:
            quality = "unavailable"
            notes.append(
                (
                    "No active holding date has complete historical close coverage "
                    "for every position in the currency."
                ),
            )

        return PortfolioCurrencyPerformance(
            currency=currency,
            position_count=len(historical_instrument_ids),
            quality=quality,
            first_observed_on=first_observed_on,
            last_observed_on=last_observed_on,
            observation_count=len(points),
            return_count=max(len(points) - 1, 0),
            initial_value=initial_value,
            latest_value=latest_value,
            period_return=period_return,
            external_cash_flow_adjusted_period_return=(
                external_cash_flow_adjusted_period_return
            ),
            external_cash_flow_count=external_cash_flow_count,
            external_net_cash_flow=external_net_cash_flow,
            points=tuple(points),
            sources=sources,
            notes=tuple(notes),
        )

    @staticmethod
    def _qualifying_cash_flows(
        *,
        currency: str,
        first_observed_on: date,
        last_observed_on: date,
        cash_flows: Sequence,
    ) -> tuple:
        first_day_end = PortfolioPerformanceService._utc_day_end(
            first_observed_on,
        )
        last_day_end = PortfolioPerformanceService._utc_day_end(
            last_observed_on,
        )

        qualifying = []

        for cash_flow in cash_flows:
            if cash_flow.currency != currency:
                continue

            effective_at = cash_flow.effective_at.astimezone(UTC)

            if first_day_end < effective_at <= last_day_end:
                qualifying.append(cash_flow)

        return tuple(qualifying)

    @staticmethod
    def _net_external_cash_flow(
        cash_flows: Sequence,
    ) -> Decimal:
        net_flow = Decimal("0")

        for cash_flow in cash_flows:
            if cash_flow.event_type == "deposit":
                net_flow += cash_flow.amount
            elif cash_flow.event_type == "withdrawal":
                net_flow -= cash_flow.amount
            else:
                raise RuntimeError(
                    "Historical portfolio cash-flow history contains an invalid "
                    "event type.",
                )

        return net_flow

    @staticmethod
    def _build_external_cash_flow_adjusted_return(
        *,
        initial_value: Decimal,
        latest_value: Decimal,
        point_count: int,
        state_changed_after_first_observation: bool,
        period_return: Decimal | None,
        external_net_cash_flow: Decimal,
        external_cash_flow_count: int,
    ) -> Decimal | None:
        if initial_value <= 0 or point_count < 2:
            return None

        if not state_changed_after_first_observation:
            return period_return

        if external_cash_flow_count == 0:
            return None

        adjusted_latest_value = latest_value - external_net_cash_flow

        if adjusted_latest_value < 0:
            return None

        return (adjusted_latest_value / initial_value) - Decimal("1")

    @staticmethod
    def _position_signature(
        position: PortfolioHistoricalPosition,
    ) -> tuple[Decimal, Decimal]:
        """Return economically relevant holding state for change detection."""

        return (
            position.quantity,
            position.average_cost,
        )

    @staticmethod
    def _has_position_change_after_first_observation(
        *,
        currency: str,
        first_observed_on: date,
        last_observed_on: date,
        historical_states,
    ) -> bool:
        first_day_end = PortfolioPerformanceService._utc_day_end(
            first_observed_on,
        )
        last_day_end = PortfolioPerformanceService._utc_day_end(
            last_observed_on,
        )

        first_state = next(
            (
                state
                for state in historical_states
                if state.as_of.date() == first_observed_on
            ),
            None,
        )

        if first_state is None:
            return False

        previous_positions = {
            position.instrument_id: PortfolioPerformanceService._position_signature(
                position,
            )
            for position in first_state.positions
            if position.currency == currency
        }

        for state in historical_states:
            if state.as_of <= first_day_end:
                continue

            if state.as_of > last_day_end:
                break

            current_positions = {
                position.instrument_id: PortfolioPerformanceService._position_signature(
                    position,
                )
                for position in state.positions
                if position.currency == currency
            }

            if current_positions != previous_positions:
                return True

            previous_positions = current_positions

        return False

    @staticmethod
    def _unavailable_result(
        *,
        portfolio: Portfolio,
        assessment_time: datetime,
        lookback_start: datetime,
        lookback_days: int,
        position_histories,
        instruments,
    ) -> PortfolioPerformance:
        notes = (
            "No historical market-data observations are available "
            "for instruments in the portfolio history.",
        )

        currencies = tuple(
            PortfolioCurrencyPerformance(
                currency=currency,
                position_count=1,
                quality="unavailable",
                first_observed_on=None,
                last_observed_on=None,
                observation_count=0,
                return_count=0,
                initial_value=None,
                latest_value=None,
                period_return=None,
                external_cash_flow_adjusted_period_return=None,
                external_cash_flow_count=0,
                external_net_cash_flow=Decimal("0"),
                points=(),
                sources=(),
                notes=notes,
            )
            for currency in sorted(
                {instrument.currency for instrument in instruments.values()},
            )
        )

        quality: PerformanceQuality = "unavailable" if currencies else "empty"

        return PortfolioPerformance(
            portfolio=portfolio,
            assessed_at=assessment_time,
            lookback_start=lookback_start,
            lookback_end=assessment_time,
            lookback_days=lookback_days,
            position_count=portfolio.position_count,
            quality=quality,
            methodology=PortfolioPerformanceService._methodology(),
            currencies=currencies,
        )

    @staticmethod
    def _select_daily_closes(
        bars: Sequence[Bar],
    ) -> tuple[
        dict[date, tuple[datetime, Decimal]],
        set[str],
    ]:
        """Reduce historical bars to the final close observed on each UTC date."""

        daily_bars: dict[date, tuple[datetime, Decimal]] = {}
        sources: set[str] = set()

        for bar in bars:
            timestamp = bar.timestamp.astimezone(UTC)
            observed_day = timestamp.date()

            current = daily_bars.get(observed_day)

            if current is None or timestamp > current[0]:
                daily_bars[observed_day] = (
                    timestamp,
                    bar.close,
                )

            sources.add(bar.source)

        return daily_bars, sources

    @staticmethod
    def _utc_day_end(observed_on: date) -> datetime:
        return datetime.combine(
            observed_on,
            time.max,
            tzinfo=UTC,
        )

    @staticmethod
    def _aggregate_quality(
        currencies: tuple[PortfolioCurrencyPerformance, ...],
    ) -> PerformanceQuality:
        """Aggregate currency quality without hiding insufficient data."""

        if not currencies:
            return "empty"

        qualities = {item.quality for item in currencies}

        if qualities == {"sufficient"}:
            return "sufficient"

        if qualities == {"unavailable"}:
            return "unavailable"

        return "insufficient"

    @staticmethod
    def _validate_aware_datetime(
        value: datetime,
        label: str,
    ) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware")

    @staticmethod
    def _methodology() -> str:
        """Describe the time-aware historical portfolio-performance methodology."""

        return (
            "Time-aware historical portfolio values reconstructed from append-only "
            "position history at UTC day-end, paired with daily closing prices and "
            "calculated separately by currency. Position changes are reflected in "
            "the value series. Simple period return remains available only when "
            "holdings remain unchanged after the first complete observation. When "
            "holdings change and recorded external cash flows exist in the same "
            "period, an explicitly labeled external cash-flow-adjusted return "
            "proxy is calculated from the net recorded flow. This proxy assumes "
            "the external flow explains the corresponding change in invested value "
            "and is not a substitute for a trade-level time-weighted return."
        )

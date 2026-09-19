from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from math import sqrt
from statistics import stdev
from typing import Literal
from uuid import UUID

from app.market_data.models import Bar
from app.market_data.providers.errors import MarketDataProviderError
from app.market_data.service import MarketDataService
from app.portfolio.cash_flow_persistence import (
    PortfolioCashFlowPersistenceService,
)
from app.portfolio.history import PortfolioHistoricalStateService
from app.portfolio.history_models import PortfolioHistoricalPosition
from app.portfolio.models import Portfolio
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.risk_metrics_models import (
    PortfolioCurrencyRiskMetrics,
    PortfolioRiskMetrics,
)

ANNUALIZATION_FACTOR = 252

RiskMetricsQuality = Literal[
    "sufficient",
    "insufficient",
    "unavailable",
    "empty",
]


@dataclass(frozen=True)
class _HistoricalPositionData:
    """Historical market data for one instrument."""

    daily_closes: dict[date, tuple[datetime, Decimal]]
    sources: frozenset[str]


@dataclass(frozen=True)
class _CurrencyObservation:
    """One complete historical currency valuation."""

    observed_on: date
    value: Decimal
    state_signature: tuple[tuple[UUID, Decimal], ...]
    segment_id: int


def calculate_annualized_volatility(
    daily_returns: Sequence[float],
) -> float | None:
    """Calculate annualized volatility from simple daily returns."""

    if len(daily_returns) < 2:
        return None

    return stdev(daily_returns) * sqrt(ANNUALIZATION_FACTOR)


def calculate_maximum_drawdown(
    values: Sequence[float],
) -> tuple[float | None, int | None, int | None]:
    """Calculate maximum drawdown and its peak/trough positions."""

    if not values:
        return None, None, None

    peak_value = values[0]
    peak_index = 0

    maximum_drawdown = 0.0
    drawdown_peak_index = 0
    drawdown_trough_index = 0

    for index, value in enumerate(values):
        if value > peak_value:
            peak_value = value
            peak_index = index

        if peak_value <= 0:
            continue

        drawdown = (value / peak_value) - 1.0

        if drawdown < maximum_drawdown:
            maximum_drawdown = drawdown
            drawdown_peak_index = peak_index
            drawdown_trough_index = index

    return (
        maximum_drawdown,
        drawdown_peak_index,
        drawdown_trough_index,
    )


def _build_flow_adjusted_segments(
    observations: Sequence[_CurrencyObservation],
    cash_flows: Sequence,
) -> tuple[tuple[tuple[date, Decimal], ...], ...]:
    """Build value segments with recorded external cash flows neutralized."""

    segments: list[tuple[tuple[date, Decimal], ...]] = []
    current_segment: list[tuple[date, Decimal]] = []

    current_segment_id: int | None = None
    cumulative_external_flow = Decimal("0")
    previous_day_end: datetime | None = None

    for observation in observations:
        if current_segment_id != observation.segment_id:
            if current_segment:
                segments.append(tuple(current_segment))

            current_segment = []
            current_segment_id = observation.segment_id
            cumulative_external_flow = Decimal("0")
            previous_day_end = PortfolioRiskMetricsService._utc_day_end(
                observation.observed_on,
            )

            adjusted_value = observation.value
        else:
            current_day_end = PortfolioRiskMetricsService._utc_day_end(
                observation.observed_on,
            )

            cumulative_external_flow += _net_external_cash_flow_between(
                cash_flows,
                start_at=previous_day_end,
                end_at=current_day_end,
            )

            adjusted_value = observation.value - cumulative_external_flow
            previous_day_end = current_day_end

        current_segment.append(
            (
                observation.observed_on,
                adjusted_value,
            ),
        )

    if current_segment:
        segments.append(tuple(current_segment))

    return tuple(segments)


def _returns_from_segments(
    segments: Sequence[Sequence[tuple[date, Decimal]]],
) -> list[float]:
    """Build simple returns from flow-adjusted comparable segments."""

    returns: list[float] = []

    for segment in segments:
        previous_value: Decimal | None = None

        for _observed_on, value in segment:
            if previous_value is not None and previous_value > 0 and value >= 0:
                returns.append(float(value / previous_value - 1))

            previous_value = value

    return returns


def _drawdown_from_segments(
    segments: Sequence[Sequence[tuple[date, Decimal]]],
) -> tuple[float | None, date | None, date | None]:
    """Find drawdown without crossing holding-state boundaries."""

    maximum_drawdown: float | None = None
    maximum_peak_date: date | None = None
    maximum_trough_date: date | None = None

    for segment in segments:
        if not segment:
            continue

        if any(value <= 0 for _observed_on, value in segment):
            continue

        segment_values = [float(value) for _observed_on, value in segment]
        segment_dates = [observed_on for observed_on, _value in segment]

        drawdown, peak_index, trough_index = calculate_maximum_drawdown(
            segment_values,
        )

        if drawdown is None:
            continue

        if maximum_drawdown is None or drawdown < maximum_drawdown:
            maximum_drawdown = drawdown
            maximum_peak_date = (
                segment_dates[peak_index] if peak_index is not None else None
            )
            maximum_trough_date = (
                segment_dates[trough_index] if trough_index is not None else None
            )

    return (
        maximum_drawdown,
        maximum_peak_date,
        maximum_trough_date,
    )


def _build_segmented_returns(
    observations: Sequence[_CurrencyObservation],
    cash_flows: Sequence = (),
) -> list[float]:
    """Build returns from flow-adjusted values within comparable segments."""

    segments = _build_flow_adjusted_segments(
        observations,
        cash_flows,
    )

    return _returns_from_segments(segments)


def _build_segmented_drawdown(
    observations: Sequence[_CurrencyObservation],
    cash_flows: Sequence = (),
) -> tuple[float | None, date | None, date | None]:
    """Find deepest flow-adjusted drawdown without crossing state changes."""

    segments = _build_flow_adjusted_segments(
        observations,
        cash_flows,
    )

    return _drawdown_from_segments(segments)


def _net_external_cash_flow_between(
    cash_flows: Sequence,
    *,
    start_at: datetime | None,
    end_at: datetime,
) -> Decimal:
    """Return net external flow after one observation and through the next."""

    net_flow = Decimal("0")

    for cash_flow in cash_flows:
        effective_at = cash_flow.effective_at

        if effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise RuntimeError(
                "Historical portfolio cash-flow timestamps must be timezone-aware.",
            )

        effective_at = effective_at.astimezone(UTC)

        if start_at is not None and effective_at <= start_at:
            continue

        if effective_at > end_at:
            continue

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


def _observed_external_cash_flows(
    cash_flows: Sequence,
    *,
    first_observed_on: date,
    last_observed_on: date,
) -> tuple:
    """Return flows after the first observation and through the last."""

    first_day_end = PortfolioRiskMetricsService._utc_day_end(
        first_observed_on,
    )
    last_day_end = PortfolioRiskMetricsService._utc_day_end(
        last_observed_on,
    )

    observed: list = []

    for cash_flow in cash_flows:
        effective_at = cash_flow.effective_at

        if effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise RuntimeError(
                "Historical portfolio cash-flow timestamps must be timezone-aware.",
            )

        effective_at = effective_at.astimezone(UTC)

        if first_day_end < effective_at <= last_day_end:
            observed.append(cash_flow)

    return tuple(observed)


def _cash_flow_net_amount(
    cash_flows: Sequence,
) -> Decimal:
    """Calculate net deposits minus withdrawals."""

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


class PortfolioRiskMetricsService:
    """Build historical risk metrics from time-aware portfolio holdings."""

    def __init__(
        self,
        persistence: PortfolioPersistenceService,
        market_data: MarketDataService,
        cash_flow_persistence: PortfolioCashFlowPersistenceService | None = None,
    ) -> None:
        self.persistence = persistence
        self.market_data = market_data
        self.cash_flow_persistence = (
            cash_flow_persistence
            if cash_flow_persistence is not None
            else PortfolioCashFlowPersistenceService(
                persistence.session,
            )
        )
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
    ) -> PortfolioRiskMetrics:
        """Build currency-separated historical portfolio risk metrics."""

        if lookback_days <= 0:
            raise ValueError("lookback_days must be greater than zero")

        assessment_time = assessed_at or datetime.now(UTC)

        self._validate_aware_datetime(
            assessment_time,
            "assessed_at",
        )

        assessment_time = assessment_time.astimezone(UTC)

        lookback_start = assessment_time - timedelta(days=lookback_days)

        detail = await self.persistence.get_detail_for_user(
            user_id,
            portfolio_id,
        )

        if detail is None:
            raise ValueError("Portfolio not found.")

        portfolio_record, position_count, _position_records = detail

        portfolio = Portfolio(
            portfolio_id=portfolio_record.id,
            name=portfolio_record.name,
            created_at=portfolio_record.created_at,
            updated_at=portfolio_record.updated_at,
            position_count=position_count,
        )

        history_records = await self.persistence.list_position_history_for_window(
            user_id=user_id,
            portfolio_id=portfolio_id,
            start_at=lookback_start,
            end_at=assessment_time,
        )

        if not history_records:
            return PortfolioRiskMetrics(
                portfolio=portfolio,
                assessed_at=assessment_time,
                lookback_start=lookback_start,
                lookback_end=assessment_time,
                lookback_days=lookback_days,
                annualization_factor=ANNUALIZATION_FACTOR,
                position_count=position_count,
                quality="empty",
                methodology=self._methodology(),
                currencies=(),
            )

        cash_flow_records = await self.cash_flow_persistence.list_for_user(
            user_id=user_id,
            portfolio_id=portfolio_id,
            start_at=lookback_start,
            end_at=assessment_time,
            limit=None,
        )

        cash_flows_by_currency = self._group_cash_flows_by_currency(
            cash_flow_records,
        )

        historical_instrument_ids = tuple(
            sorted(
                {record.instrument_id for record in history_records},
                key=str,
            ),
        )

        instrument_data: dict[UUID, _HistoricalPositionData] = {}
        candidate_days: set[date] = set()

        for instrument_id in historical_instrument_ids:
            try:
                bars = await self.market_data.get_historical_bars(
                    instrument_id,
                    lookback_start,
                    assessment_time,
                )
            except MarketDataProviderError:
                bars = ()

            daily_closes, sources = self._select_daily_closes(bars)

            instrument_data[instrument_id] = _HistoricalPositionData(
                daily_closes=daily_closes,
                sources=frozenset(sources),
            )
            candidate_days.update(daily_closes)

        candidate_days.update(
            self._event_dates(history_records),
        )

        if not candidate_days:
            return PortfolioRiskMetrics(
                portfolio=portfolio,
                assessed_at=assessment_time,
                lookback_start=lookback_start,
                lookback_end=assessment_time,
                lookback_days=lookback_days,
                annualization_factor=ANNUALIZATION_FACTOR,
                position_count=position_count,
                quality="unavailable",
                methodology=self._methodology(),
                currencies=(),
            )

        as_ofs = tuple(
            datetime.combine(
                observed_day,
                time.max,
                tzinfo=UTC,
            )
            for observed_day in sorted(candidate_days)
        )

        historical_states = await self.historical_state.build_many(
            user_id,
            portfolio_id,
            as_ofs=as_ofs,
        )

        currency_metrics = self._build_currency_metrics(
            historical_states,
            instrument_data,
            cash_flows_by_currency,
        )

        return PortfolioRiskMetrics(
            portfolio=portfolio,
            assessed_at=assessment_time,
            lookback_start=lookback_start,
            lookback_end=assessment_time,
            lookback_days=lookback_days,
            annualization_factor=ANNUALIZATION_FACTOR,
            position_count=position_count,
            quality=self._aggregate_quality(currency_metrics),
            methodology=self._methodology(),
            currencies=currency_metrics,
        )

    @staticmethod
    def _group_cash_flows_by_currency(
        cash_flows: Sequence,
    ) -> dict[str, tuple]:
        grouped: dict[str, list] = defaultdict(list)

        for cash_flow in cash_flows:
            grouped[cash_flow.currency].append(cash_flow)

        return {currency: tuple(events) for currency, events in grouped.items()}

    def _build_currency_metrics(
        self,
        historical_states,
        instrument_data: dict[UUID, _HistoricalPositionData],
        cash_flows_by_currency: dict[str, tuple],
    ) -> tuple[PortfolioCurrencyRiskMetrics, ...]:
        """Build currency metrics from complete time-aware observations."""

        observations_by_currency: dict[
            str,
            list[_CurrencyObservation],
        ] = defaultdict(list)

        sources_by_currency: dict[str, set[str]] = defaultdict(set)
        all_currencies: set[str] = set()
        position_counts_by_currency: dict[str, int] = defaultdict(int)
        segment_ids: dict[str, int] = defaultdict(int)

        previous_signatures: dict[
            str,
            tuple[tuple[UUID, Decimal], ...] | None,
        ] = {}

        for state in historical_states:
            positions_by_currency = self._group_positions_by_currency(
                state.positions,
            )

            active_currencies = set(positions_by_currency)
            known_currencies = all_currencies | active_currencies

            for currency in known_currencies - active_currencies:
                if currency in previous_signatures:
                    segment_ids[currency] += 1
                    previous_signatures[currency] = None

            for currency, positions in positions_by_currency.items():
                all_currencies.add(currency)
                position_counts_by_currency[currency] = max(
                    position_counts_by_currency[currency],
                    len(positions),
                )

                state_signature = self._state_signature(positions)

                if (
                    currency in previous_signatures
                    and previous_signatures[currency] != state_signature
                ):
                    segment_ids[currency] += 1

                previous_signatures[currency] = state_signature

                observed_day = state.as_of.date()

                complete = all(
                    (
                        position.instrument_id in instrument_data
                        and observed_day
                        in instrument_data[position.instrument_id].daily_closes
                    )
                    for position in positions
                )

                if not complete:
                    segment_ids[currency] += 1
                    previous_signatures[currency] = None
                    continue

                value = Decimal("0")

                for position in positions:
                    market_data = instrument_data[position.instrument_id]
                    _, close = market_data.daily_closes[observed_day]
                    value += position.quantity * close
                    sources_by_currency[currency].update(
                        market_data.sources,
                    )

                observations_by_currency[currency].append(
                    _CurrencyObservation(
                        observed_on=observed_day,
                        value=value,
                        state_signature=state_signature,
                        segment_id=segment_ids[currency],
                    ),
                )

        metrics: list[PortfolioCurrencyRiskMetrics] = []

        for currency in sorted(all_currencies):
            observations = tuple(
                sorted(
                    observations_by_currency[currency],
                    key=lambda item: item.observed_on,
                ),
            )

            metrics.append(
                self._build_currency_metric(
                    currency=currency,
                    observations=observations,
                    position_count=position_counts_by_currency[currency],
                    sources=tuple(
                        sorted(sources_by_currency[currency]),
                    ),
                    cash_flows=cash_flows_by_currency.get(currency, ()),
                ),
            )

        return tuple(metrics)

    @staticmethod
    def _build_currency_metric(
        *,
        currency: str,
        observations: tuple[_CurrencyObservation, ...],
        position_count: int,
        sources: tuple[str, ...],
        cash_flows: Sequence = (),
    ) -> PortfolioCurrencyRiskMetrics:
        if not observations:
            return PortfolioCurrencyRiskMetrics(
                currency=currency,
                position_count=position_count,
                quality="unavailable",
                first_observed_on=None,
                last_observed_on=None,
                observation_count=0,
                return_count=0,
                annualized_volatility=None,
                maximum_drawdown=None,
                drawdown_peak_on=None,
                drawdown_trough_on=None,
                sources=sources,
                notes=(
                    (
                        "Historical position states exist, but no dates have "
                        "complete market-close coverage for this currency."
                    ),
                ),
            )

        flow_adjusted_segments = _build_flow_adjusted_segments(
            observations,
            cash_flows,
        )

        daily_returns = _returns_from_segments(
            flow_adjusted_segments,
        )

        annualized_volatility = calculate_annualized_volatility(
            daily_returns,
        )

        (
            maximum_drawdown,
            drawdown_peak_on,
            drawdown_trough_on,
        ) = _drawdown_from_segments(
            flow_adjusted_segments,
        )

        first_observed_on = observations[0].observed_on
        last_observed_on = observations[-1].observed_on

        observed_cash_flows = _observed_external_cash_flows(
            cash_flows,
            first_observed_on=first_observed_on,
            last_observed_on=last_observed_on,
        )

        external_cash_flow_net = _cash_flow_net_amount(
            observed_cash_flows,
        )

        has_nonpositive_adjusted_value = any(
            value <= 0
            for segment in flow_adjusted_segments
            for _observed_on, value in segment
        )

        notes = [
            (
                "Historical quantities are reconstructed from the append-only "
                "position history."
            ),
            "No synthetic prices are created for missing historical observations.",
            (
                "Portfolio values are calculated separately for each currency; "
                "no FX conversion is performed."
            ),
            (
                "Annualized volatility uses the sample standard deviation of "
                "flow-adjusted simple returns multiplied by sqrt(252)."
            ),
            (
                "Recorded external deposits and withdrawals are neutralized "
                "within unchanged holding-state intervals using their effective "
                "timestamps."
            ),
            (
                "Holding-state changes remain segmentation boundaries because "
                "trade-level purchases, sales, dividends, and internal cash "
                "movements are not persisted as transaction records."
            ),
        ]

        if observed_cash_flows:
            notes.append(
                (
                    "Recorded external cash flows after the first complete "
                    "observation and through the last were considered: "
                    f"{len(observed_cash_flows)} event(s), net "
                    f"{external_cash_flow_net} {currency}."
                ),
            )
        else:
            notes.append(
                (
                    "No recorded external cash flows were present within "
                    "the observed period."
                ),
            )

        if has_nonpositive_adjusted_value:
            notes.append(
                (
                    "One or more flow-adjusted observations were non-positive; "
                    "affected intervals were omitted from risk calculations where "
                    "a positive comparison base was required."
                ),
            )

        if len(daily_returns) < 2:
            quality: RiskMetricsQuality = "insufficient"
            notes.append(
                (
                    "At least three comparable complete observations with valid "
                    "positive comparison bases are required to calculate "
                    "sample-based annualized volatility."
                ),
            )
        else:
            quality = "sufficient"

        if any(
            left.segment_id != right.segment_id
            for left, right in zip(
                observations,
                observations[1:],
                strict=False,
            )
        ):
            notes.append(
                (
                    "At least one historical holding-state change occurred; "
                    "risk calculations were segmented at those boundaries."
                ),
            )

        return PortfolioCurrencyRiskMetrics(
            currency=currency,
            position_count=position_count,
            quality=quality,
            first_observed_on=first_observed_on,
            last_observed_on=last_observed_on,
            observation_count=len(observations),
            return_count=len(daily_returns),
            annualized_volatility=annualized_volatility,
            maximum_drawdown=maximum_drawdown,
            drawdown_peak_on=drawdown_peak_on,
            drawdown_trough_on=drawdown_trough_on,
            sources=sources,
            notes=tuple(notes),
        )

    @staticmethod
    def _group_positions_by_currency(
        positions: Sequence[PortfolioHistoricalPosition],
    ) -> dict[str, tuple[PortfolioHistoricalPosition, ...]]:
        grouped: dict[
            str,
            list[PortfolioHistoricalPosition],
        ] = defaultdict(list)

        for position in positions:
            grouped[position.currency].append(position)

        return {
            currency: tuple(
                sorted(
                    currency_positions,
                    key=lambda item: str(item.instrument_id),
                ),
            )
            for currency, currency_positions in grouped.items()
        }

    @staticmethod
    def _state_signature(
        positions: Sequence[PortfolioHistoricalPosition],
    ) -> tuple[tuple[UUID, Decimal], ...]:
        return tuple(
            sorted(
                (
                    position.instrument_id,
                    position.quantity,
                )
                for position in positions
            )
        )

    @staticmethod
    def _event_dates(history_records) -> set[date]:
        return {record.recorded_at.astimezone(UTC).date() for record in history_records}

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
    def _aggregate_quality(
        metrics: tuple[PortfolioCurrencyRiskMetrics, ...],
    ) -> RiskMetricsQuality:
        """Aggregate currency quality without hiding insufficient data."""

        if not metrics:
            return "empty"

        qualities = {item.quality for item in metrics}

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
    def _utc_day_end(observed_on: date) -> datetime:
        return datetime.combine(
            observed_on,
            time.max,
            tzinfo=UTC,
        )

    @staticmethod
    def _methodology() -> str:
        """Describe the time-aware historical methodology."""

        return (
            "Time-aware historical portfolio risk analysis using reconstructed "
            "position states, daily closing prices, simple returns, annualized "
            "sample volatility, and maximum drawdown. Currency series remain "
            "separate, and recorded external deposits and withdrawals are "
            "neutralized within unchanged holding-state intervals using their "
            "effective timestamps. Holding-state changes remain segmentation "
            "boundaries because trade-level transaction data is not persisted."
        )

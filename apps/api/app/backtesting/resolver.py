from bisect import bisect_left, bisect_right
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.engine import BacktestSignal
from app.backtesting.horizon import BacktestHorizon
from app.backtesting.market_data_quality import (
    BacktestMarketDataHorizonQuality,
    build_market_data_horizon_quality,
)
from app.backtesting.models import BacktestPeriod, TimeAwareObservation
from app.db.models.instrument import Instrument
from app.db.models.market_bar import MarketBar
from app.db.models.signal import SignalRecord
from app.evaluation.models import (
    EvaluationDirection,
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)
from app.market_data.repository import MarketDataRepository


class BacktestDataResolutionError(ValueError):
    """Raised when persisted backtest data cannot be resolved safely."""


class BacktestDataResolutionResult:
    """Resolved historical inputs for server-side backtest execution."""

    def __init__(
        self,
        *,
        signals: tuple[BacktestSignal, ...],
        observations: tuple[TimeAwareObservation, ...],
        market_data_expected_count: int | None = None,
        market_data_resolved_count: int | None = None,
        market_data_horizon_quality: (
            tuple[BacktestMarketDataHorizonQuality, ...] | None
        ) = None,
        notes: tuple[str, ...] = (),
    ) -> None:
        self.signals = signals
        self.observations = observations
        self.market_data_expected_count = market_data_expected_count
        self.market_data_resolved_count = market_data_resolved_count
        self.market_data_horizon_quality = market_data_horizon_quality
        self.notes = notes

    @property
    def market_data_coverage_ratio(self) -> float | None:
        if self.market_data_expected_count in (None, 0):
            return None

        if self.market_data_resolved_count is None:
            return None

        return min(
            self.market_data_resolved_count / self.market_data_expected_count,
            1.0,
        )


class BacktestDataResolver:
    """Resolve persisted signals and market bars into backtest inputs."""

    _HORIZON_MAP = {
        "short_term": BacktestHorizon.ONE_DAY,
        "medium_term": BacktestHorizon.FIVE_DAYS,
        "long_term": BacktestHorizon.TWENTY_DAYS,
    }

    _RECOMMENDATION_STATE_MAP = {
        "opportunity": EvaluationRecommendationState.CONSIDER,
        "watch": EvaluationRecommendationState.WATCH,
        "hold": EvaluationRecommendationState.HOLD,
        "reduce": EvaluationRecommendationState.REDUCE,
        "insufficient_evidence": (EvaluationRecommendationState.INSUFFICIENT_EVIDENCE),
    }

    def __init__(
        self,
        market_data_repository: MarketDataRepository | None = None,
    ) -> None:
        self.market_data_repository = market_data_repository

    async def resolve(
        self,
        session: AsyncSession,
        *,
        evaluation_periods: tuple[BacktestPeriod, ...] | list[BacktestPeriod],
        benchmark_instrument_id: UUID | None = None,
    ) -> BacktestDataResolutionResult:
        evaluation_periods = tuple(evaluation_periods)

        if not evaluation_periods:
            raise BacktestDataResolutionError(
                "At least one evaluation period is required.",
            )

        if benchmark_instrument_id is not None:
            benchmark = await session.get(
                Instrument,
                benchmark_instrument_id,
            )

            if benchmark is None:
                raise BacktestDataResolutionError(
                    f"Benchmark instrument {benchmark_instrument_id} was not found.",
                )

        signals = await self._load_signals(
            session,
            evaluation_periods,
        )

        if not signals:
            market_data_quality = build_market_data_horizon_quality(
                expected_by_horizon={},
                resolved_by_horizon={},
            )

            return BacktestDataResolutionResult(
                signals=(),
                observations=(),
                market_data_expected_count=0,
                market_data_resolved_count=0,
                market_data_horizon_quality=market_data_quality,
                notes=(
                    "No persisted market signals were found in the "
                    "requested evaluation periods.",
                ),
            )

        resolved_signals: list[BacktestSignal] = []
        skipped_uncertain = 0

        for record in signals:
            horizon = self._map_horizon(record.time_horizon)

            if horizon is None:
                skipped_uncertain += 1
                continue

            resolved_signals.append(
                BacktestSignal(
                    signal_id=record.id,
                    event_id=record.event_id,
                    instrument_id=record.instrument_id,
                    created_at=record.created_at,
                    direction=EvaluationDirection(record.direction),
                    signal_strength=EvaluationSignalStrength(record.strength),
                    recommendation_state=self._map_recommendation_state(
                        record.opportunity,
                    ),
                    confidence=record.confidence,
                    horizons=(horizon,),
                ),
            )

        if not resolved_signals:
            notes = [
                "No persisted signals had a deterministic backtest horizon.",
            ]

            if skipped_uncertain:
                notes.append(
                    f"Skipped {skipped_uncertain} signal(s) with uncertain "
                    "time horizons.",
                )

            market_data_quality = build_market_data_horizon_quality(
                expected_by_horizon={},
                resolved_by_horizon={},
            )

            return BacktestDataResolutionResult(
                signals=(),
                observations=(),
                market_data_expected_count=0,
                market_data_resolved_count=0,
                market_data_horizon_quality=market_data_quality,
                notes=tuple(notes),
            )

        observations, resolved_market_data_count = await self._resolve_observations(
            session,
            resolved_signals,
            benchmark_instrument_id=benchmark_instrument_id,
        )

        expected_by_horizon: dict[BacktestHorizon, int] = {
            horizon: 0 for horizon in BacktestHorizon
        }
        resolved_by_horizon: dict[BacktestHorizon, int] = {
            horizon: 0 for horizon in BacktestHorizon
        }

        for signal in resolved_signals:
            horizon = self._horizon_for_signal(signal)
            expected_by_horizon[horizon] += 1

        for observation in observations:
            if observation.horizon is not None:
                resolved_by_horizon[observation.horizon] += 1

        market_data_horizon_quality = build_market_data_horizon_quality(
            expected_by_horizon=expected_by_horizon,
            resolved_by_horizon=resolved_by_horizon,
        )

        market_data_expected_count = sum(expected_by_horizon.values())

        notes: list[str] = [
            "Signals were resolved from persisted historical signal snapshots.",
            "Forward observations were resolved from persisted market bars.",
            "Entry bars must occur strictly after signal creation.",
            "Target bars are selected at or after the requested horizon.",
            "Forward returns are calculated from entry close to target close.",
            (
                "Market-data quality is assessed independently for each "
                "deterministic backtest horizon."
            ),
        ]

        if benchmark_instrument_id is None:
            notes.append(
                "Benchmark returns are unavailable because no benchmark "
                "instrument was configured.",
            )
        else:
            notes.append(
                "Benchmark returns were resolved from the persisted benchmark "
                "market bars using the same signal timestamp and horizon.",
            )
            notes.append(
                "Relative return is calculated as target return minus "
                "benchmark return.",
            )

        if skipped_uncertain:
            notes.append(
                f"Skipped {skipped_uncertain} signal(s) with uncertain time horizons.",
            )

        notes.append(
            "Market-data coverage thresholds are evaluated independently "
            "from backtest evaluation-quality thresholds.",
        )

        return BacktestDataResolutionResult(
            signals=tuple(resolved_signals),
            observations=observations,
            market_data_expected_count=market_data_expected_count,
            market_data_resolved_count=resolved_market_data_count,
            market_data_horizon_quality=market_data_horizon_quality,
            notes=tuple(notes),
        )

    async def _load_signals(
        self,
        session: AsyncSession,
        evaluation_periods: tuple[BacktestPeriod, ...],
    ) -> tuple[SignalRecord, ...]:
        minimum_start = min(period.start_at for period in evaluation_periods)
        maximum_end = max(period.end_at for period in evaluation_periods)

        result = await session.execute(
            select(SignalRecord)
            .where(
                SignalRecord.created_at >= minimum_start,
                SignalRecord.created_at < maximum_end,
            )
            .order_by(
                SignalRecord.created_at,
                SignalRecord.id,
            ),
        )

        records = tuple(result.scalars().all())

        return tuple(
            record
            for record in records
            if any(
                period.start_at <= record.created_at < period.end_at
                for period in evaluation_periods
            )
        )

    async def _resolve_observations(
        self,
        session: AsyncSession,
        signals: list[BacktestSignal],
        *,
        benchmark_instrument_id: UUID | None,
    ) -> tuple[tuple[TimeAwareObservation, ...], int]:
        repository = self._get_market_data_repository(session)

        target_instrument_ids = tuple(
            {signal.instrument_id for signal in signals},
        )

        minimum_signal_time = min(signal.created_at for signal in signals)

        maximum_target_time = max(
            signal.created_at
            + timedelta(
                days=self._horizon_for_signal(signal).days,
            )
            for signal in signals
        )

        target_bars = await repository.get_historical_bars_for_instruments(
            instrument_ids=target_instrument_ids,
            start_after=minimum_signal_time,
            end_at=maximum_target_time,
        )

        benchmark_bars: dict[UUID, list[MarketBar]] = {}

        if benchmark_instrument_id is not None:
            benchmark_bars = await repository.get_historical_bars_for_instruments(
                instrument_ids=(benchmark_instrument_id,),
                start_after=minimum_signal_time,
                end_at=maximum_target_time,
            )

        observations: list[TimeAwareObservation] = []

        for signal in signals:
            instrument_bars = target_bars.get(
                signal.instrument_id,
                [],
            )

            if not instrument_bars:
                continue

            horizon = self._horizon_for_signal(signal)

            benchmark_instrument_bars = benchmark_bars.get(
                benchmark_instrument_id,
                [],
            )

            observation = self._build_observation(
                signal=signal,
                horizon=horizon,
                bars=instrument_bars,
                benchmark_bars=benchmark_instrument_bars,
            )

            if observation is not None:
                observations.append(observation)

        return tuple(observations), len(observations)

    def _get_market_data_repository(
        self,
        session: AsyncSession,
    ) -> MarketDataRepository:
        """Return the configured repository or create a session-bound one."""
        return self.market_data_repository or MarketDataRepository(session)

    @classmethod
    def _map_horizon(
        cls,
        time_horizon: str,
    ) -> BacktestHorizon | None:
        return cls._HORIZON_MAP.get(time_horizon)

    @classmethod
    def _map_recommendation_state(
        cls,
        opportunity: str,
    ) -> EvaluationRecommendationState:
        try:
            return cls._RECOMMENDATION_STATE_MAP[opportunity]
        except KeyError as exc:
            raise BacktestDataResolutionError(
                f"Unsupported persisted recommendation state: {opportunity}",
            ) from exc

    @staticmethod
    def _horizon_for_signal(
        signal: BacktestSignal,
    ) -> BacktestHorizon:
        if len(signal.horizons) != 1:
            raise BacktestDataResolutionError(
                f"Signal {signal.signal_id} must have exactly one "
                "deterministic backtest horizon.",
            )

        return signal.horizons[0]

    @staticmethod
    def _build_observation(
        *,
        signal: BacktestSignal,
        horizon: BacktestHorizon,
        bars: list[MarketBar],
        benchmark_bars: list[MarketBar],
    ) -> TimeAwareObservation | None:
        timestamps = [bar.timestamp for bar in bars]

        entry_index = bisect_right(
            timestamps,
            signal.created_at,
        )

        if entry_index >= len(bars):
            return None

        entry_bar = bars[entry_index]

        target_at = signal.created_at + timedelta(
            days=horizon.days,
        )

        target_index = bisect_left(
            timestamps,
            target_at,
        )

        if target_index >= len(bars):
            return None

        target_bar = bars[target_index]

        if target_bar.timestamp <= entry_bar.timestamp:
            return None

        if entry_bar.close <= 0 or target_bar.close <= 0:
            return None

        forward_return_pct = float(
            (target_bar.close / entry_bar.close - 1) * 100,
        )

        benchmark_return_pct = None

        if benchmark_bars:
            benchmark_return_pct = BacktestDataResolver._calculate_benchmark_return(
                signal_created_at=signal.created_at,
                target_at=target_at,
                bars=benchmark_bars,
            )

        return TimeAwareObservation(
            instrument_id=signal.instrument_id,
            observed_at=target_bar.timestamp,
            forward_return_pct=round(forward_return_pct, 6),
            benchmark_return_pct=benchmark_return_pct,
            horizon=horizon,
        )

    @staticmethod
    def _calculate_benchmark_return(
        *,
        signal_created_at,
        target_at,
        bars: list[MarketBar],
    ) -> float | None:
        timestamps = [bar.timestamp for bar in bars]

        entry_index = bisect_right(
            timestamps,
            signal_created_at,
        )

        target_index = bisect_left(
            timestamps,
            target_at,
        )

        if entry_index >= len(bars):
            return None

        if target_index >= len(bars):
            return None

        entry_bar = bars[entry_index]
        target_bar = bars[target_index]

        if target_bar.timestamp <= entry_bar.timestamp:
            return None

        if entry_bar.close <= 0 or target_bar.close <= 0:
            return None

        return round(
            float(
                (target_bar.close / entry_bar.close - 1) * 100,
            ),
            6,
        )


__all__ = [
    "BacktestDataResolutionError",
    "BacktestDataResolutionResult",
    "BacktestDataResolver",
]

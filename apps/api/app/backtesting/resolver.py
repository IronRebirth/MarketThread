from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.engine import BacktestSignal
from app.backtesting.horizon import BacktestHorizon
from app.backtesting.models import BacktestPeriod, TimeAwareObservation
from app.db.models.market_bar import MarketBar
from app.db.models.signal import SignalRecord
from app.evaluation.models import (
    EvaluationDirection,
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)


class BacktestDataResolutionError(ValueError):
    """Raised when persisted backtest data cannot be resolved safely."""


class BacktestDataResolutionResult:
    """Resolved historical inputs for server-side backtest execution."""

    def __init__(
        self,
        *,
        signals: tuple[BacktestSignal, ...],
        observations: tuple[TimeAwareObservation, ...],
        notes: tuple[str, ...] = (),
    ) -> None:
        self.signals = signals
        self.observations = observations
        self.notes = notes


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

    async def resolve(
        self,
        session: AsyncSession,
        *,
        evaluation_periods: tuple[BacktestPeriod, ...] | list[BacktestPeriod],
    ) -> BacktestDataResolutionResult:
        evaluation_periods = tuple(evaluation_periods)

        if not evaluation_periods:
            raise BacktestDataResolutionError(
                "At least one evaluation period is required.",
            )

        signals = await self._load_signals(
            session,
            evaluation_periods,
        )

        if not signals:
            return BacktestDataResolutionResult(
                signals=(),
                observations=(),
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

            return BacktestDataResolutionResult(
                signals=(),
                observations=(),
                notes=tuple(notes),
            )

        observations = await self._resolve_observations(
            session,
            resolved_signals,
        )

        notes: list[str] = [
            "Signals were resolved from persisted historical signal snapshots.",
            "Forward observations were resolved from persisted market bars.",
            "Entry bars must occur strictly after signal creation.",
            "Target bars are selected at or after the requested horizon.",
            "Forward returns are calculated from entry close to target close.",
            "Benchmark returns are unavailable because no persisted benchmark "
            "series is configured.",
        ]

        if skipped_uncertain:
            notes.append(
                f"Skipped {skipped_uncertain} signal(s) with uncertain time horizons.",
            )

        return BacktestDataResolutionResult(
            signals=tuple(resolved_signals),
            observations=observations,
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
    ) -> tuple[TimeAwareObservation, ...]:
        instrument_ids = tuple({signal.instrument_id for signal in signals})

        minimum_signal_time = min(signal.created_at for signal in signals)

        maximum_target_time = max(
            signal.created_at + timedelta(days=self._horizon_for_signal(signal).days)
            for signal in signals
        )

        result = await session.execute(
            select(MarketBar)
            .where(
                MarketBar.instrument_id.in_(instrument_ids),
                MarketBar.timestamp > minimum_signal_time,
                MarketBar.timestamp <= maximum_target_time,
            )
            .order_by(
                MarketBar.instrument_id,
                MarketBar.timestamp,
            ),
        )

        bars = tuple(result.scalars().all())

        bars_by_instrument: dict[UUID, list[MarketBar]] = defaultdict(list)

        for bar in bars:
            bars_by_instrument[bar.instrument_id].append(bar)

        observations: list[TimeAwareObservation] = []

        for signal in signals:
            instrument_bars = bars_by_instrument.get(
                signal.instrument_id,
                [],
            )

            if not instrument_bars:
                continue

            horizon = self._horizon_for_signal(signal)

            observation = self._build_observation(
                signal=signal,
                horizon=horizon,
                bars=instrument_bars,
            )

            if observation is not None:
                observations.append(observation)

        return tuple(observations)

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

        return TimeAwareObservation(
            instrument_id=signal.instrument_id,
            observed_at=target_bar.timestamp,
            forward_return_pct=round(forward_return_pct, 6),
            benchmark_return_pct=None,
            horizon=horizon,
        )


__all__ = [
    "BacktestDataResolutionError",
    "BacktestDataResolutionResult",
    "BacktestDataResolver",
]

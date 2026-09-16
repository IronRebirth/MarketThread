from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .horizon import BacktestHorizon

MarketDataQualityState = Literal[
    "sufficient",
    "insufficient",
    "unavailable",
    "not_assessed",
]


class BacktestMarketDataHorizonQuality(BaseModel):
    """Market-data resolution quality for one deterministic backtest horizon."""

    model_config = ConfigDict(frozen=True)

    horizon: BacktestHorizon
    expected_count: int
    resolved_count: int
    coverage_ratio: float | None = None
    quality_state: MarketDataQualityState
    warnings: tuple[str, ...] = ()


def assess_market_data_horizon_quality(
    *,
    horizon: BacktestHorizon,
    expected_count: int,
    resolved_count: int,
) -> BacktestMarketDataHorizonQuality:
    """Assess usable market-data coverage for a single horizon."""

    if expected_count < 0:
        raise ValueError("expected_count must be non-negative.")

    if resolved_count < 0:
        raise ValueError("resolved_count must be non-negative.")

    if resolved_count > expected_count:
        raise ValueError("resolved_count cannot exceed expected_count.")

    if expected_count == 0:
        return BacktestMarketDataHorizonQuality(
            horizon=horizon,
            expected_count=0,
            resolved_count=0,
            coverage_ratio=None,
            quality_state="unavailable",
            warnings=("No deterministic signals were available for this horizon.",),
        )

    coverage_ratio = min(resolved_count / expected_count, 1.0)

    if resolved_count == 0:
        return BacktestMarketDataHorizonQuality(
            horizon=horizon,
            expected_count=expected_count,
            resolved_count=resolved_count,
            coverage_ratio=0.0,
            quality_state="insufficient",
            warnings=(
                "No deterministic signals received usable market-data observations.",
            ),
        )

    if coverage_ratio < 0.95:
        return BacktestMarketDataHorizonQuality(
            horizon=horizon,
            expected_count=expected_count,
            resolved_count=resolved_count,
            coverage_ratio=coverage_ratio,
            quality_state="insufficient",
            warnings=(
                "Market-data coverage for this horizon is below the 95% "
                "minimum threshold.",
            ),
        )

    return BacktestMarketDataHorizonQuality(
        horizon=horizon,
        expected_count=expected_count,
        resolved_count=resolved_count,
        coverage_ratio=coverage_ratio,
        quality_state="sufficient",
        warnings=(),
    )


def build_market_data_horizon_quality(
    *,
    expected_by_horizon: Mapping[BacktestHorizon, int],
    resolved_by_horizon: Mapping[BacktestHorizon, int],
) -> tuple[BacktestMarketDataHorizonQuality, ...]:
    """Build deterministic quality assessments for every supported horizon."""

    assessments: list[BacktestMarketDataHorizonQuality] = []

    for horizon in BacktestHorizon:
        expected_count = expected_by_horizon.get(horizon, 0)
        resolved_count = resolved_by_horizon.get(horizon, 0)

        assessments.append(
            assess_market_data_horizon_quality(
                horizon=horizon,
                expected_count=expected_count,
                resolved_count=resolved_count,
            ),
        )

    return tuple(assessments)


__all__ = [
    "BacktestMarketDataHorizonQuality",
    "MarketDataQualityState",
    "assess_market_data_horizon_quality",
    "build_market_data_horizon_quality",
]

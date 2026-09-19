from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.portfolio.risk_metrics import (
    _build_segmented_drawdown,
    _build_segmented_returns,
    _CurrencyObservation,
    calculate_annualized_volatility,
)


def build_observation(
    *,
    day: int,
    value: str,
    quantity: str,
    segment_id: int,
) -> _CurrencyObservation:
    return _CurrencyObservation(
        observed_on=date(2026, 1, day),
        value=Decimal(value),
        state_signature=((uuid4(), Decimal(quantity)),),
        segment_id=segment_id,
    )


def test_segmented_returns_ignore_holding_state_changes() -> None:
    observations = (
        build_observation(
            day=1,
            value="100",
            quantity="1",
            segment_id=0,
        ),
        build_observation(
            day=2,
            value="200",
            quantity="2",
            segment_id=1,
        ),
        build_observation(
            day=3,
            value="220",
            quantity="2",
            segment_id=1,
        ),
    )

    returns = _build_segmented_returns(observations)

    assert returns == [0.1]


def test_segmented_drawdown_does_not_cross_holding_state_change() -> None:
    observations = (
        build_observation(
            day=1,
            value="100",
            quantity="1",
            segment_id=0,
        ),
        build_observation(
            day=2,
            value="50",
            quantity="0.5",
            segment_id=1,
        ),
        build_observation(
            day=3,
            value="45",
            quantity="0.5",
            segment_id=1,
        ),
    )

    drawdown, peak_on, trough_on = _build_segmented_drawdown(
        observations,
    )

    assert drawdown == pytest.approx(-0.1)
    assert peak_on == date(2026, 1, 2)
    assert trough_on == date(2026, 1, 3)


def test_annualized_volatility_uses_segmented_market_returns() -> None:
    observations = (
        build_observation(
            day=1,
            value="100",
            quantity="1",
            segment_id=0,
        ),
        build_observation(
            day=2,
            value="110",
            quantity="1",
            segment_id=0,
        ),
        build_observation(
            day=3,
            value="121",
            quantity="1",
            segment_id=0,
        ),
        build_observation(
            day=4,
            value="133.1",
            quantity="1",
            segment_id=0,
        ),
    )

    returns = _build_segmented_returns(observations)

    assert len(returns) == 3
    assert calculate_annualized_volatility(returns) == 0.0

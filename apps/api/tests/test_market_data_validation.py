from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.market_data.models import Bar, Quote
from app.market_data.validation import (
    MarketDataValidationError,
    validate_bar,
    validate_bars,
    validate_quote,
)


def make_bar(**overrides) -> Bar:
    values = {
        "instrument_id": uuid4(),
        "timestamp": datetime(2026, 1, 2, 12, tzinfo=UTC),
        "open": Decimal("100"),
        "high": Decimal("105"),
        "low": Decimal("95"),
        "close": Decimal("102"),
        "volume": Decimal("1000"),
        "source": "test-provider",
    }
    values.update(overrides)
    return Bar(**values)


def make_quote(**overrides) -> Quote:
    values = {
        "instrument_id": uuid4(),
        "timestamp": datetime(2026, 1, 2, 12, tzinfo=UTC),
        "price": Decimal("100"),
        "bid": Decimal("99.50"),
        "ask": Decimal("100.50"),
        "volume": Decimal("1000"),
        "source": "test-provider",
    }
    values.update(overrides)
    return Quote(**values)


def test_valid_bar_passes_validation() -> None:
    bar = make_bar()

    assert validate_bar(bar) == bar


def test_valid_quote_passes_validation() -> None:
    quote = make_quote()

    assert validate_quote(quote) == quote


def test_bar_requires_high_to_cover_open_and_close() -> None:
    bar = make_bar(high=Decimal("101"))

    with pytest.raises(
        MarketDataValidationError,
        match="bar high must be greater than or equal to bar open and close",
    ):
        validate_bar(bar)


def test_bar_requires_low_to_cover_open_and_close() -> None:
    bar = make_bar(low=Decimal("101"))

    with pytest.raises(
        MarketDataValidationError,
        match="bar low must be less than or equal to bar open and close",
    ):
        validate_bar(bar)


def test_bar_rejects_negative_volume() -> None:
    bar = make_bar(volume=Decimal("-1"))

    with pytest.raises(
        MarketDataValidationError,
        match="bar volume must be greater than or equal to zero",
    ):
        validate_bar(bar)


def test_bar_rejects_non_positive_price() -> None:
    bar = make_bar(open=Decimal("0"))

    with pytest.raises(
        MarketDataValidationError,
        match="bar open must be greater than zero",
    ):
        validate_bar(bar)


def test_bar_rejects_naive_timestamp() -> None:
    bar = make_bar(
        timestamp=datetime(2026, 1, 2, 12),
    )

    with pytest.raises(
        MarketDataValidationError,
        match="bar timestamp must be timezone-aware",
    ):
        validate_bar(bar)


def test_quote_rejects_bid_above_ask() -> None:
    quote = make_quote(
        bid=Decimal("101"),
        ask=Decimal("100"),
    )

    with pytest.raises(
        MarketDataValidationError,
        match="quote bid must be less than or equal to quote ask",
    ):
        validate_quote(quote)


def test_quote_rejects_bid_above_price() -> None:
    quote = make_quote(
        bid=Decimal("101"),
        ask=Decimal("102"),
    )

    with pytest.raises(
        MarketDataValidationError,
        match="quote bid must be less than or equal to quote price",
    ):
        validate_quote(quote)


def test_quote_rejects_ask_below_price() -> None:
    quote = make_quote(
        bid=Decimal("98"),
        ask=Decimal("99"),
    )

    with pytest.raises(
        MarketDataValidationError,
        match="quote ask must be greater than or equal to quote price",
    ):
        validate_quote(quote)


def test_quote_rejects_negative_volume() -> None:
    quote = make_quote(volume=Decimal("-1"))

    with pytest.raises(
        MarketDataValidationError,
        match="quote volume must be greater than or equal to zero",
    ):
        validate_quote(quote)


def test_quote_rejects_naive_timestamp() -> None:
    quote = make_quote(
        timestamp=datetime(2026, 1, 2, 12),
    )

    with pytest.raises(
        MarketDataValidationError,
        match="quote timestamp must be timezone-aware",
    ):
        validate_quote(quote)


def test_validate_bars_returns_immutable_sequence() -> None:
    bars = (
        make_bar(),
        make_bar(
            timestamp=datetime(
                2026,
                1,
                3,
                12,
                tzinfo=UTC,
            ),
        ),
    )

    result = validate_bars(list(bars))

    assert result == bars
    assert isinstance(result, tuple)

from datetime import datetime
from decimal import Decimal

from app.market_data.models import Bar, Quote


class MarketDataValidationError(ValueError):
    """Raised when normalized market data violates domain invariants."""


def _validate_timestamp(timestamp: datetime, label: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise MarketDataValidationError(
            f"{label} timestamp must be timezone-aware",
        )


def _validate_decimal(
    value: Decimal,
    label: str,
    *,
    positive: bool = False,
    non_negative: bool = False,
) -> None:
    if not value.is_finite():
        raise MarketDataValidationError(
            f"{label} must be finite",
        )

    if positive and value <= 0:
        raise MarketDataValidationError(
            f"{label} must be greater than zero",
        )

    if non_negative and value < 0:
        raise MarketDataValidationError(
            f"{label} must be greater than or equal to zero",
        )


def validate_quote(quote: Quote) -> Quote:
    """Validate a normalized market quote."""

    _validate_timestamp(quote.timestamp, "quote")

    _validate_decimal(
        quote.price,
        "quote price",
        positive=True,
    )

    if quote.bid is not None:
        _validate_decimal(
            quote.bid,
            "quote bid",
            positive=True,
        )

    if quote.ask is not None:
        _validate_decimal(
            quote.ask,
            "quote ask",
            positive=True,
        )

    if quote.volume is not None:
        _validate_decimal(
            quote.volume,
            "quote volume",
            non_negative=True,
        )

    if quote.bid is not None and quote.ask is not None:
        if quote.bid > quote.ask:
            raise MarketDataValidationError(
                "quote bid must be less than or equal to quote ask",
            )

    if quote.bid is not None and quote.bid > quote.price:
        raise MarketDataValidationError(
            "quote bid must be less than or equal to quote price",
        )

    if quote.ask is not None and quote.ask < quote.price:
        raise MarketDataValidationError(
            "quote ask must be greater than or equal to quote price",
        )

    return quote


def validate_bar(bar: Bar) -> Bar:
    """Validate a normalized OHLCV market bar."""

    _validate_timestamp(bar.timestamp, "bar")

    _validate_decimal(
        bar.open,
        "bar open",
        positive=True,
    )
    _validate_decimal(
        bar.high,
        "bar high",
        positive=True,
    )
    _validate_decimal(
        bar.low,
        "bar low",
        positive=True,
    )
    _validate_decimal(
        bar.close,
        "bar close",
        positive=True,
    )

    if bar.volume is not None:
        _validate_decimal(
            bar.volume,
            "bar volume",
            non_negative=True,
        )

    if bar.high < bar.low:
        raise MarketDataValidationError(
            "bar high must be greater than or equal to bar low",
        )

    if bar.high < bar.open or bar.high < bar.close:
        raise MarketDataValidationError(
            "bar high must be greater than or equal to bar open and close",
        )

    if bar.low > bar.open or bar.low > bar.close:
        raise MarketDataValidationError(
            "bar low must be less than or equal to bar open and close",
        )

    return bar


def validate_bars(bars: list[Bar] | tuple[Bar, ...]) -> tuple[Bar, ...]:
    """Validate a collection of normalized market bars."""

    validated: list[Bar] = []

    for bar in bars:
        validated.append(validate_bar(bar))

    return tuple(validated)

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import ceil

from app.market_data.models import (
    Bar,
    HistoricalDataCompleteness,
    Quote,
    QuoteFreshness,
)


class MarketDataQualityError(ValueError):
    """Raised when market-data quality cannot be assessed safely."""


def assess_quote_freshness(
    quote: Quote | None,
    *,
    assessed_at: datetime | None = None,
    maximum_age: timedelta = timedelta(minutes=15),
) -> QuoteFreshness:
    """Assess whether a quote is recent enough for downstream use."""

    if maximum_age.total_seconds() <= 0:
        raise MarketDataQualityError(
            "maximum quote age must be greater than zero",
        )

    assessment_time = assessed_at or datetime.now(UTC)

    _validate_aware_datetime(
        assessment_time,
        "assessment timestamp",
    )

    if quote is None:
        return QuoteFreshness(
            status="unavailable",
            observed_at=None,
            assessed_at=assessment_time,
            age_seconds=None,
            maximum_age_seconds=maximum_age.total_seconds(),
        )

    _validate_aware_datetime(
        quote.timestamp,
        "quote timestamp",
    )

    age_seconds = (assessment_time - quote.timestamp).total_seconds()

    if age_seconds < 0:
        raise MarketDataQualityError(
            "quote timestamp is in the future relative to assessment time",
        )

    status = "fresh" if age_seconds <= maximum_age.total_seconds() else "stale"

    return QuoteFreshness(
        status=status,
        observed_at=quote.timestamp,
        assessed_at=assessment_time,
        age_seconds=age_seconds,
        maximum_age_seconds=maximum_age.total_seconds(),
        source=quote.source,
    )


def assess_historical_completeness(
    bars: Sequence[Bar],
    *,
    start: datetime,
    end: datetime,
    expected_interval: timedelta,
    minimum_coverage: float = 0.95,
) -> HistoricalDataCompleteness:
    """Assess observed bar coverage for an explicit expected interval."""

    _validate_aware_datetime(start, "start timestamp")
    _validate_aware_datetime(end, "end timestamp")

    if start >= end:
        raise MarketDataQualityError(
            "start must be earlier than end",
        )

    interval_seconds = expected_interval.total_seconds()

    if interval_seconds <= 0:
        raise MarketDataQualityError(
            "expected interval must be greater than zero",
        )

    if not 0 < minimum_coverage <= 1:
        raise MarketDataQualityError(
            "minimum coverage must be greater than zero and at most one",
        )

    timestamps = sorted(
        {bar.timestamp for bar in bars if start <= bar.timestamp < end},
    )

    expected_bars = max(
        1,
        ceil(
            (end - start).total_seconds() / interval_seconds,
        ),
    )

    observed_bars = len(timestamps)
    missing_bars = max(
        expected_bars - observed_bars,
        0,
    )

    coverage_ratio = min(
        observed_bars / expected_bars,
        1.0,
    )

    if observed_bars == 0:
        status = "unavailable"
    elif coverage_ratio >= minimum_coverage:
        status = "sufficient"
    else:
        status = "insufficient"

    sources = tuple(
        sorted(
            {bar.source for bar in bars if start <= bar.timestamp < end},
        ),
    )

    return HistoricalDataCompleteness(
        status=status,
        start=start,
        end=end,
        expected_interval_seconds=interval_seconds,
        minimum_coverage=minimum_coverage,
        expected_bars=expected_bars,
        observed_bars=observed_bars,
        missing_bars=missing_bars,
        coverage_ratio=coverage_ratio,
        first_observed_at=timestamps[0] if timestamps else None,
        last_observed_at=timestamps[-1] if timestamps else None,
        sources=sources,
    )


def _validate_aware_datetime(
    value: datetime,
    label: str,
) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MarketDataQualityError(
            f"{label} must be timezone-aware",
        )

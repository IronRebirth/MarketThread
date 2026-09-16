from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.market_data.models import Bar, Quote
from app.market_data.quality import (
    MarketDataQualityError,
    assess_historical_completeness,
    assess_quote_freshness,
)


def make_quote(timestamp: datetime) -> Quote:
    return Quote(
        instrument_id=uuid4(),
        timestamp=timestamp,
        price=Decimal("100"),
        bid=Decimal("99"),
        ask=Decimal("101"),
        volume=Decimal("1000"),
        source="test-provider",
    )


def make_bar(timestamp: datetime) -> Bar:
    return Bar(
        instrument_id=uuid4(),
        timestamp=timestamp,
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("95"),
        close=Decimal("102"),
        volume=Decimal("1000"),
        source="test-provider",
    )


def test_quote_is_fresh_when_within_maximum_age() -> None:
    assessed_at = datetime(
        2026,
        1,
        2,
        12,
        0,
        tzinfo=UTC,
    )
    quote = make_quote(
        assessed_at - timedelta(minutes=5),
    )

    result = assess_quote_freshness(
        quote,
        assessed_at=assessed_at,
        maximum_age=timedelta(minutes=15),
    )

    assert result.status == "fresh"
    assert result.age_seconds == 300
    assert result.maximum_age_seconds == 900


def test_quote_is_stale_when_older_than_maximum_age() -> None:
    assessed_at = datetime(
        2026,
        1,
        2,
        12,
        0,
        tzinfo=UTC,
    )
    quote = make_quote(
        assessed_at - timedelta(minutes=30),
    )

    result = assess_quote_freshness(
        quote,
        assessed_at=assessed_at,
        maximum_age=timedelta(minutes=15),
    )

    assert result.status == "stale"
    assert result.age_seconds == 1800


def test_missing_quote_is_unavailable() -> None:
    assessed_at = datetime(
        2026,
        1,
        2,
        12,
        0,
        tzinfo=UTC,
    )

    result = assess_quote_freshness(
        None,
        assessed_at=assessed_at,
    )

    assert result.status == "unavailable"
    assert result.observed_at is None
    assert result.age_seconds is None


def test_future_quote_timestamp_is_rejected() -> None:
    assessed_at = datetime(
        2026,
        1,
        2,
        12,
        0,
        tzinfo=UTC,
    )
    quote = make_quote(
        assessed_at + timedelta(minutes=1),
    )

    with pytest.raises(
        MarketDataQualityError,
        match="quote timestamp is in the future",
    ):
        assess_quote_freshness(
            quote,
            assessed_at=assessed_at,
        )


def test_historical_coverage_is_sufficient() -> None:
    start = datetime(
        2026,
        1,
        1,
        0,
        0,
        tzinfo=UTC,
    )
    end = start + timedelta(hours=24)

    bars = [make_bar(start + timedelta(hours=offset)) for offset in range(24)]

    result = assess_historical_completeness(
        bars,
        start=start,
        end=end,
        expected_interval=timedelta(hours=1),
    )

    assert result.status == "sufficient"
    assert result.expected_bars == 24
    assert result.observed_bars == 24
    assert result.missing_bars == 0
    assert result.coverage_ratio == 1
    assert result.sources == ("test-provider",)


def test_historical_coverage_is_insufficient_when_bars_are_missing() -> None:
    start = datetime(
        2026,
        1,
        1,
        0,
        0,
        tzinfo=UTC,
    )
    end = start + timedelta(hours=24)

    bars = [make_bar(start + timedelta(hours=offset)) for offset in range(20)]

    result = assess_historical_completeness(
        bars,
        start=start,
        end=end,
        expected_interval=timedelta(hours=1),
        minimum_coverage=0.95,
    )

    assert result.status == "insufficient"
    assert result.expected_bars == 24
    assert result.observed_bars == 20
    assert result.missing_bars == 4
    assert result.coverage_ratio == pytest.approx(20 / 24)


def test_historical_coverage_is_unavailable_without_bars() -> None:
    start = datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )
    end = start + timedelta(days=1)

    result = assess_historical_completeness(
        [],
        start=start,
        end=end,
        expected_interval=timedelta(hours=1),
    )

    assert result.status == "unavailable"
    assert result.observed_bars == 0
    assert result.missing_bars == 24
    assert result.coverage_ratio == 0
    assert result.first_observed_at is None
    assert result.last_observed_at is None


def test_duplicate_timestamps_count_once() -> None:
    start = datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )
    end = start + timedelta(hours=3)

    first = make_bar(start)
    duplicate = first.model_copy(update={"source": "second-provider"})
    second = make_bar(start + timedelta(hours=1))
    third = make_bar(start + timedelta(hours=2))

    result = assess_historical_completeness(
        [
            first,
            duplicate,
            second,
            third,
        ],
        start=start,
        end=end,
        expected_interval=timedelta(hours=1),
    )

    assert result.observed_bars == 3
    assert result.coverage_ratio == 1
    assert result.sources == (
        "second-provider",
        "test-provider",
    )


def test_quality_rejects_naive_start_timestamp() -> None:
    start = datetime(2026, 1, 1)
    end = datetime(
        2026,
        1,
        2,
        tzinfo=UTC,
    )

    with pytest.raises(
        MarketDataQualityError,
        match="start timestamp must be timezone-aware",
    ):
        assess_historical_completeness(
            [],
            start=start,
            end=end,
            expected_interval=timedelta(hours=1),
        )


def test_quality_rejects_invalid_coverage_threshold() -> None:
    start = datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )
    end = start + timedelta(hours=1)

    with pytest.raises(
        MarketDataQualityError,
        match="minimum coverage must be greater than zero and at most one",
    ):
        assess_historical_completeness(
            [],
            start=start,
            end=end,
            expected_interval=timedelta(hours=1),
            minimum_coverage=1.1,
        )

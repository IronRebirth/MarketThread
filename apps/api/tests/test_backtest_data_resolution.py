from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.backtesting.horizon import BacktestHorizon
from app.backtesting.models import BacktestPeriod
from app.backtesting.resolver import BacktestDataResolver
from app.db.models.instrument import Instrument
from app.db.models.market_bar import MarketBar
from app.db.models.signal import SignalRecord


async def create_instrument(db_session) -> Instrument:
    instrument = Instrument(
        symbol=f"TST{uuid4().hex[:8].upper()}",
        name="Resolver Test Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


async def create_signal(
    db_session,
    *,
    instrument_id,
    created_at: datetime,
    time_horizon: str,
) -> SignalRecord:
    signal = SignalRecord(
        event_id=uuid4(),
        instrument_id=instrument_id,
        company_name="Resolver Test Company",
        ticker="TEST",
        created_at=created_at,
        direction="positive",
        strength="strong",
        opportunity="opportunity",
        confidence=0.9,
        risk_score=0.2,
        time_horizon=time_horizon,
        supporting_factors=[],
        contradicting_factors=[],
        evidence_article_ids=[],
        invalidation_conditions=[],
        rationale="Resolver test signal.",
    )

    db_session.add(signal)
    await db_session.commit()
    await db_session.refresh(signal)

    return signal


async def create_bar(
    db_session,
    *,
    instrument_id,
    timestamp: datetime,
    close: str,
) -> MarketBar:
    bar = MarketBar(
        instrument_id=instrument_id,
        timestamp=timestamp,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("1000"),
        source="test",
    )

    db_session.add(bar)
    await db_session.commit()
    await db_session.refresh(bar)

    return bar


async def cleanup(db_session, instrument_id) -> None:
    await db_session.execute(
        delete(MarketBar).where(
            MarketBar.instrument_id == instrument_id,
        ),
    )
    await db_session.execute(
        delete(SignalRecord).where(
            SignalRecord.instrument_id == instrument_id,
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.id == instrument_id,
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_resolves_medium_term_signal_to_five_day_observation(db_session):
    instrument = await create_instrument(db_session)

    try:
        signal = await create_signal(
            db_session,
            instrument_id=instrument.id,
            created_at=datetime(
                2026,
                1,
                5,
                10,
                0,
                tzinfo=UTC,
            ),
            time_horizon="medium_term",
        )

        await create_bar(
            db_session,
            instrument_id=instrument.id,
            timestamp=datetime(
                2026,
                1,
                5,
                10,
                1,
                tzinfo=UTC,
            ),
            close="100",
        )
        await create_bar(
            db_session,
            instrument_id=instrument.id,
            timestamp=datetime(
                2026,
                1,
                10,
                10,
                0,
                tzinfo=UTC,
            ),
            close="110",
        )

        result = await BacktestDataResolver().resolve(
            db_session,
            evaluation_periods=(
                BacktestPeriod(
                    start_at=datetime(
                        2026,
                        1,
                        1,
                        tzinfo=UTC,
                    ),
                    end_at=datetime(
                        2026,
                        2,
                        1,
                        tzinfo=UTC,
                    ),
                ),
            ),
        )

        assert len(result.signals) == 1
        assert result.signals[0].signal_id == signal.id
        assert result.signals[0].horizons == (BacktestHorizon.FIVE_DAYS,)

        assert len(result.observations) == 1
        observation = result.observations[0]
        assert observation.observed_at == datetime(
            2026,
            1,
            10,
            10,
            0,
            tzinfo=UTC,
        )
        assert observation.forward_return_pct == 10.0
        assert observation.benchmark_return_pct is None
        assert observation.horizon == BacktestHorizon.FIVE_DAYS
    finally:
        await cleanup(db_session, instrument.id)


@pytest.mark.asyncio
async def test_excludes_uncertain_horizon(db_session):
    instrument = await create_instrument(db_session)

    try:
        await create_signal(
            db_session,
            instrument_id=instrument.id,
            created_at=datetime(
                2026,
                1,
                5,
                tzinfo=UTC,
            ),
            time_horizon="uncertain",
        )

        result = await BacktestDataResolver().resolve(
            db_session,
            evaluation_periods=(
                BacktestPeriod(
                    start_at=datetime(
                        2026,
                        1,
                        1,
                        tzinfo=UTC,
                    ),
                    end_at=datetime(
                        2026,
                        2,
                        1,
                        tzinfo=UTC,
                    ),
                ),
            ),
        )

        assert result.signals == ()
        assert result.observations == ()
        assert any("uncertain time horizons" in note for note in result.notes)
    finally:
        await cleanup(db_session, instrument.id)


@pytest.mark.asyncio
async def test_requires_entry_bar_strictly_after_signal(db_session):
    instrument = await create_instrument(db_session)

    try:
        await create_signal(
            db_session,
            instrument_id=instrument.id,
            created_at=datetime(
                2026,
                1,
                5,
                10,
                0,
                tzinfo=UTC,
            ),
            time_horizon="short_term",
        )

        await create_bar(
            db_session,
            instrument_id=instrument.id,
            timestamp=datetime(
                2026,
                1,
                5,
                10,
                0,
                tzinfo=UTC,
            ),
            close="100",
        )
        await create_bar(
            db_session,
            instrument_id=instrument.id,
            timestamp=datetime(
                2026,
                1,
                5,
                10,
                1,
                tzinfo=UTC,
            ),
            close="105",
        )
        await create_bar(
            db_session,
            instrument_id=instrument.id,
            timestamp=datetime(
                2026,
                1,
                6,
                10,
                0,
                tzinfo=UTC,
            ),
            close="110",
        )

        result = await BacktestDataResolver().resolve(
            db_session,
            evaluation_periods=(
                BacktestPeriod(
                    start_at=datetime(
                        2026,
                        1,
                        1,
                        tzinfo=UTC,
                    ),
                    end_at=datetime(
                        2026,
                        2,
                        1,
                        tzinfo=UTC,
                    ),
                ),
            ),
        )

        assert len(result.observations) == 1
        assert result.observations[0].forward_return_pct == (
            pytest.approx((110 / 105 - 1) * 100, rel=1e-6)
        )
    finally:
        await cleanup(db_session, instrument.id)


@pytest.mark.asyncio
async def test_resolves_benchmark_return(db_session):
    target_instrument = await create_instrument(db_session)

    benchmark_instrument = await create_instrument(db_session)

    try:
        await create_signal(
            db_session,
            instrument_id=target_instrument.id,
            created_at=datetime(
                2099,
                4,
                5,
                10,
                0,
                tzinfo=UTC,
            ),
            time_horizon="short_term",
        )

        await create_bar(
            db_session,
            instrument_id=target_instrument.id,
            timestamp=datetime(
                2099,
                4,
                5,
                10,
                1,
                tzinfo=UTC,
            ),
            close="100",
        )
        await create_bar(
            db_session,
            instrument_id=target_instrument.id,
            timestamp=datetime(
                2099,
                4,
                6,
                10,
                0,
                tzinfo=UTC,
            ),
            close="110",
        )

        await create_bar(
            db_session,
            instrument_id=benchmark_instrument.id,
            timestamp=datetime(
                2099,
                4,
                5,
                10,
                1,
                tzinfo=UTC,
            ),
            close="200",
        )
        await create_bar(
            db_session,
            instrument_id=benchmark_instrument.id,
            timestamp=datetime(
                2099,
                4,
                6,
                10,
                0,
                tzinfo=UTC,
            ),
            close="204",
        )

        result = await BacktestDataResolver().resolve(
            db_session,
            evaluation_periods=(
                BacktestPeriod(
                    start_at=datetime(
                        2099,
                        4,
                        1,
                        tzinfo=UTC,
                    ),
                    end_at=datetime(
                        2099,
                        5,
                        1,
                        tzinfo=UTC,
                    ),
                ),
            ),
            benchmark_instrument_id=benchmark_instrument.id,
        )

        assert len(result.observations) == 1
        observation = result.observations[0]

        assert observation.forward_return_pct == 10.0
        assert observation.benchmark_return_pct == 2.0
        assert observation.horizon == BacktestHorizon.ONE_DAY
    finally:
        await cleanup(db_session, target_instrument.id)
        await cleanup(db_session, benchmark_instrument.id)


@pytest.mark.asyncio
async def test_missing_benchmark_bars_leave_benchmark_return_unavailable(
    db_session,
):
    target_instrument = await create_instrument(db_session)
    benchmark_instrument = await create_instrument(db_session)

    try:
        await create_signal(
            db_session,
            instrument_id=target_instrument.id,
            created_at=datetime(
                2099,
                5,
                5,
                10,
                0,
                tzinfo=UTC,
            ),
            time_horizon="short_term",
        )

        await create_bar(
            db_session,
            instrument_id=target_instrument.id,
            timestamp=datetime(
                2099,
                5,
                5,
                10,
                1,
                tzinfo=UTC,
            ),
            close="100",
        )
        await create_bar(
            db_session,
            instrument_id=target_instrument.id,
            timestamp=datetime(
                2099,
                5,
                6,
                10,
                0,
                tzinfo=UTC,
            ),
            close="105",
        )

        result = await BacktestDataResolver().resolve(
            db_session,
            evaluation_periods=(
                BacktestPeriod(
                    start_at=datetime(
                        2099,
                        5,
                        1,
                        tzinfo=UTC,
                    ),
                    end_at=datetime(
                        2099,
                        6,
                        1,
                        tzinfo=UTC,
                    ),
                ),
            ),
            benchmark_instrument_id=benchmark_instrument.id,
        )

        assert len(result.observations) == 1
        assert result.observations[0].benchmark_return_pct is None
    finally:
        await cleanup(db_session, target_instrument.id)
        await cleanup(db_session, benchmark_instrument.id)

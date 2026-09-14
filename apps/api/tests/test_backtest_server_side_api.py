from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from app.db.models.backtest import (
    BacktestEvaluation,
    BacktestFold,
    BacktestRun,
)
from app.db.models.instrument import Instrument
from app.db.models.market_bar import MarketBar
from app.db.models.signal import SignalRecord


async def create_instrument(
    db_session,
    *,
    name: str,
    symbol_prefix: str,
) -> Instrument:
    instrument = Instrument(
        symbol=f"{symbol_prefix}{uuid4().hex[:8].upper()}",
        name=name,
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


async def create_fixture_data(db_session):
    instrument = await create_instrument(
        db_session,
        name="Server Side Test Instrument",
        symbol_prefix="TST",
    )
    benchmark = await create_instrument(
        db_session,
        name="Server Side Benchmark Instrument",
        symbol_prefix="BMK",
    )

    signal = SignalRecord(
        event_id=uuid4(),
        instrument_id=instrument.id,
        company_name="Server Side Test Company",
        ticker="SST",
        created_at=datetime(
            2099,
            2,
            2,
            10,
            0,
            tzinfo=UTC,
        ),
        direction="positive",
        strength="strong",
        opportunity="opportunity",
        confidence=0.9,
        risk_score=0.2,
        time_horizon="short_term",
        supporting_factors=[],
        contradicting_factors=[],
        evidence_article_ids=[],
        invalidation_conditions=[],
        rationale="Server-side API test signal.",
    )

    db_session.add(signal)

    target_bars = (
        MarketBar(
            instrument_id=instrument.id,
            timestamp=datetime(
                2099,
                2,
                2,
                10,
                1,
                tzinfo=UTC,
            ),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("1000"),
            source="test",
        ),
        MarketBar(
            instrument_id=instrument.id,
            timestamp=datetime(
                2099,
                2,
                3,
                10,
                0,
                tzinfo=UTC,
            ),
            open=Decimal("105"),
            high=Decimal("106"),
            low=Decimal("104"),
            close=Decimal("105"),
            volume=Decimal("1000"),
            source="test",
        ),
    )

    benchmark_bars = (
        MarketBar(
            instrument_id=benchmark.id,
            timestamp=datetime(
                2099,
                2,
                2,
                10,
                1,
                tzinfo=UTC,
            ),
            open=Decimal("200"),
            high=Decimal("201"),
            low=Decimal("199"),
            close=Decimal("200"),
            volume=Decimal("2000"),
            source="test",
        ),
        MarketBar(
            instrument_id=benchmark.id,
            timestamp=datetime(
                2099,
                2,
                3,
                10,
                0,
                tzinfo=UTC,
            ),
            open=Decimal("202"),
            high=Decimal("203"),
            low=Decimal("201"),
            close=Decimal("202"),
            volume=Decimal("2000"),
            source="test",
        ),
    )

    db_session.add_all(
        (*target_bars, *benchmark_bars),
    )
    await db_session.commit()

    return instrument, benchmark, signal


async def cleanup(
    db_session,
    instrument_id: UUID,
    benchmark_id: UUID,
    backtest_id: UUID | None,
) -> None:
    await db_session.rollback()

    if backtest_id is not None:
        fold_result = await db_session.execute(
            BacktestFold.__table__.select().where(
                BacktestFold.backtest_id == backtest_id,
            ),
        )

        fold_ids = tuple(row.id for row in fold_result)

        if fold_ids:
            await db_session.execute(
                delete(BacktestEvaluation).where(
                    BacktestEvaluation.fold_id.in_(fold_ids),
                ),
            )

        await db_session.execute(
            delete(BacktestFold).where(
                BacktestFold.backtest_id == backtest_id,
            ),
        )
        await db_session.execute(
            delete(BacktestRun).where(
                BacktestRun.id == backtest_id,
            ),
        )

    await db_session.execute(
        delete(SignalRecord).where(
            SignalRecord.instrument_id == instrument_id,
        ),
    )
    await db_session.execute(
        delete(MarketBar).where(
            MarketBar.instrument_id.in_(
                (instrument_id, benchmark_id),
            ),
        ),
    )
    await db_session.execute(
        delete(Instrument).where(
            Instrument.id.in_(
                (instrument_id, benchmark_id),
            ),
        ),
    )

    await db_session.commit()


@pytest.mark.asyncio
async def test_execute_server_side_backtest_resolves_database_inputs(
    client,
    db_session,
):
    instrument, benchmark, signal = await create_fixture_data(db_session)
    backtest_id = None

    try:
        response = await client.post(
            "/backtests/execute-server-side",
            json={
                "training_periods": [
                    {
                        "start_at": "2099-01-01T00:00:00Z",
                        "end_at": "2099-02-01T00:00:00Z",
                    },
                ],
                "evaluation_periods": [
                    {
                        "start_at": "2099-02-01T00:00:00Z",
                        "end_at": "2099-03-01T00:00:00Z",
                    },
                ],
                "benchmark_instrument_id": str(benchmark.id),
            },
        )

        assert response.status_code == 201

        payload = response.json()
        backtest_id = UUID(payload["run"]["backtest_id"])

        assert payload["run"]["valid"] is True
        assert payload["run"]["evaluation_count"] == 1
        assert payload["run"]["valid_evaluation_count"] == 1

        assert payload["report"]["total_evaluations"] == 1
        assert payload["report"]["average_forward_return_pct"] == 5.0
        assert payload["report"]["average_relative_return_pct"] == 4.0
        assert payload["report"]["directional_accuracy"] == 1.0

        persisted_evaluations = await db_session.execute(
            BacktestEvaluation.__table__.select().where(
                BacktestEvaluation.signal_id == signal.id,
            ),
        )
        evaluation_rows = tuple(persisted_evaluations)

        assert len(evaluation_rows) == 1
        assert evaluation_rows[0].instrument_id == instrument.id
        assert evaluation_rows[0].forward_return_pct == 5.0
        assert evaluation_rows[0].benchmark_return_pct == 1.0
        assert evaluation_rows[0].relative_return_pct == 4.0
    finally:
        await cleanup(
            db_session,
            instrument.id,
            benchmark.id,
            backtest_id,
        )


@pytest.mark.asyncio
async def test_execute_server_side_backtest_rejects_unknown_benchmark(
    client,
    db_session,
):
    instrument, benchmark, _ = await create_fixture_data(db_session)

    try:
        response = await client.post(
            "/backtests/execute-server-side",
            json={
                "training_periods": [
                    {
                        "start_at": "2099-01-01T00:00:00Z",
                        "end_at": "2099-02-01T00:00:00Z",
                    },
                ],
                "evaluation_periods": [
                    {
                        "start_at": "2099-02-01T00:00:00Z",
                        "end_at": "2099-03-01T00:00:00Z",
                    },
                ],
                "benchmark_instrument_id": str(uuid4()),
            },
        )

        assert response.status_code == 422
        assert "Benchmark instrument" in response.json()["detail"]
    finally:
        await cleanup(
            db_session,
            instrument.id,
            benchmark.id,
            None,
        )

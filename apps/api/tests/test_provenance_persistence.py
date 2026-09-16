from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.backtest import BacktestRun
from app.provenance.models import AnalysisStage, ProvenanceRecord
from app.provenance.persistence import (
    ProvenanceAlreadyExistsError,
    ProvenanceNotFoundError,
    ProvenancePersistenceService,
)


def make_record() -> ProvenanceRecord:
    timestamp = datetime.now(UTC)

    return ProvenanceRecord(
        result_id=uuid4(),
        stage=AnalysisStage.BACKTESTING,
        created_at=timestamp,
        ruleset_version="1.0.0",
        input_ids=(uuid4(), uuid4()),
        assumptions=("Historical observations are immutable.",),
        invalidation_conditions=("The execution ruleset changes.",),
    )


async def create_backtest_run(
    db_session: AsyncSession,
    backtest_id,
) -> None:
    db_session.add(
        BacktestRun(
            id=backtest_id,
            valid=True,
            evaluation_count=0,
            valid_evaluation_count=0,
            rejected_evaluation_count=0,
            market_data_expected_count=None,
            market_data_resolved_count=None,
            market_data_coverage_ratio=None,
            market_data_horizon_quality=None,
            notes=[],
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_persists_and_restores_backtest_provenance(
    db_session: AsyncSession,
) -> None:
    backtest_id = uuid4()

    await create_backtest_run(
        db_session,
        backtest_id,
    )

    record = make_record().model_copy(
        update={"result_id": backtest_id},
    )

    service = ProvenancePersistenceService()

    await service.save(
        db_session,
        record,
    )

    restored = await service.get(
        db_session,
        backtest_id,
    )

    assert restored == record


@pytest.mark.asyncio
async def test_duplicate_provenance_is_rejected(
    db_session: AsyncSession,
) -> None:
    backtest_id = uuid4()

    await create_backtest_run(
        db_session,
        backtest_id,
    )

    record = make_record().model_copy(
        update={"result_id": backtest_id},
    )

    service = ProvenancePersistenceService()

    await service.save(
        db_session,
        record,
    )

    with pytest.raises(ProvenanceAlreadyExistsError):
        await service.save(
            db_session,
            record,
        )


@pytest.mark.asyncio
async def test_missing_provenance_is_rejected(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ProvenanceNotFoundError):
        await ProvenancePersistenceService().get(
            db_session,
            uuid4(),
        )

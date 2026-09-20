from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.model_monitoring_snapshot import ModelMonitoringSnapshot

from .models import ModelMonitoringReport, ModelMonitoringReportResponse


class ModelMonitoringPersistenceService:
    async def create(
        self,
        session: AsyncSession,
        report: ModelMonitoringReport,
    ) -> ModelMonitoringSnapshot:
        record = ModelMonitoringSnapshot(
            id=report.snapshot_id,
            model_name=report.model_name,
            model_version=report.model_version,
            window_start=report.window_start,
            window_end=report.window_end,
            observed_at=report.observed_at,
            metrics=report.model_dump(mode="json"),
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    async def list(
        self,
        session: AsyncSession,
        *,
        model_name: str | None,
        limit: int,
        offset: int,
    ) -> tuple[tuple[ModelMonitoringSnapshot, ...], int]:
        statement = select(ModelMonitoringSnapshot)
        count_statement = select(func.count(ModelMonitoringSnapshot.id))
        if model_name is not None:
            statement = statement.where(ModelMonitoringSnapshot.model_name == model_name)
            count_statement = count_statement.where(ModelMonitoringSnapshot.model_name == model_name)
        statement = statement.order_by(ModelMonitoringSnapshot.observed_at.desc()).offset(offset).limit(limit)
        result = await session.execute(statement)
        total = await session.scalar(count_statement)
        return tuple(result.scalars().all()), int(total or 0)

    def to_response(self, record: ModelMonitoringSnapshot) -> ModelMonitoringReportResponse:
        report = ModelMonitoringReport.model_validate(record.metrics)
        return ModelMonitoringReportResponse(
            **report.model_dump(),
            created_at=record.created_at,
        )

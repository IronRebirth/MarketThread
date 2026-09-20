from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

from .models import ModelMonitoringReportListResponse, ModelMonitoringReportResponse, ModelMonitoringRequest
from .persistence import ModelMonitoringPersistenceService
from .service import ModelMonitoringService

router = APIRouter(prefix="/model-monitoring", tags=["model-monitoring"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
_service = ModelMonitoringService()
_persistence = ModelMonitoringPersistenceService()


@router.post(
    "/reports",
    response_model=ModelMonitoringReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_monitoring_report(
    request: ModelMonitoringRequest,
    session: DatabaseSession,
) -> ModelMonitoringReportResponse:
    report = _service.build_report(request)
    record = await _persistence.create(session, report)
    return _persistence.to_response(record)


@router.get(
    "/reports",
    response_model=ModelMonitoringReportListResponse,
)
async def list_monitoring_reports(
    session: DatabaseSession,
    model_name: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ModelMonitoringReportListResponse:
    records, total = await _persistence.list(
        session,
        model_name=model_name,
        limit=limit,
        offset=offset,
    )
    return ModelMonitoringReportListResponse(
        reports=tuple(_persistence.to_response(record) for record in records),
        total=total,
        limit=limit,
        offset=offset,
    )

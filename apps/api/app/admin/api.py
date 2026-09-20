from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.core.config import get_settings
from app.db.session import get_db_session

from .models import AdminAuditLogListResponse, AdminSystemHealth
from .service import AdminService

router = APIRouter(prefix="/admin", tags=["administration"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
_service = AdminService()


def require_admin(current_user: CurrentUser) -> CurrentUser:
    """Require the authenticated user to have administrator privileges."""

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )

    return current_user


@router.get("/health", response_model=AdminSystemHealth)
async def get_admin_health(
    session: DatabaseSession,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
) -> AdminSystemHealth:
    """Return provider, data, and system health for administrators."""

    await _service.record_audit(
        session,
        actor_user_id=current_user.id,
        action="admin.health.viewed",
        resource_type="system_health",
    )

    return await _service.system_health(session, get_settings())


@router.get("/audit-logs", response_model=AdminAuditLogListResponse)
async def list_admin_audit_logs(
    session: DatabaseSession,
    current_user: Annotated[CurrentUser, Depends(require_admin)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminAuditLogListResponse:
    """Return recent administrative audit records."""

    await _service.record_audit(
        session,
        actor_user_id=current_user.id,
        action="admin.audit_logs.viewed",
        resource_type="audit_log",
    )

    return await _service.list_audit_logs(
        session,
        limit=limit,
        offset=offset,
    )

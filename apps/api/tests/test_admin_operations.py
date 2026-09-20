from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.admin.service import AdminService
from app.db.models.user import User


@pytest.mark.asyncio
async def test_admin_service_reports_unconfigured_optional_providers(
    db_session,
) -> None:
    service = AdminService()

    health = await service.system_health(
        db_session,
        type(
            "SettingsStub",
            (),
            {
                "market_data_base_url": None,
                "market_data_api_key": None,
                "news_api_key": None,
                "news_api_base_url": "https://news.example",
                "llm_api_key": None,
                "smtp_host": None,
                "smtp_from_email": None,
            },
        )(),
    )

    assert health.database == "healthy"
    assert health.background_jobs == "not_configured"
    assert {provider.name: provider.status for provider in health.providers} == {
        "market_data": "unconfigured",
        "news": "unconfigured",
        "llm": "unconfigured",
        "smtp": "unconfigured",
    }


@pytest.mark.asyncio
async def test_admin_audit_log_is_persisted(db_session) -> None:
    user = User(
        id=uuid4(),
        email=f"admin-{uuid4()}@example.com",
        password_hash="hash",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()

    service = AdminService()
    record = await service.record_audit(
        db_session,
        actor_user_id=user.id,
        action="admin.test",
        resource_type="test",
        detail={"checked_at": datetime.now(UTC).isoformat()},
    )

    response = await service.list_audit_logs(
        db_session,
        limit=10,
        offset=0,
    )

    assert response.total >= 1
    assert response.entries[0].id == record.id

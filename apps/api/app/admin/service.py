from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.admin_audit_log import AdminAuditLogRecord
from app.db.models.event import EventRecord
from app.db.models.fundamental_snapshot import FundamentalSnapshot
from app.db.models.instrument import Instrument
from app.db.models.market_bar import MarketBar
from app.db.models.market_data import MarketQuote
from app.db.models.model_monitoring_snapshot import ModelMonitoringSnapshot
from app.db.models.news import NewsArticle
from app.db.models.recommendation import RecommendationRecord
from app.db.models.signal import SignalRecord
from app.market_data.providers.errors import MarketDataProviderError
from app.market_data.providers.factory import create_market_data_provider
from app.news.providers.errors import NewsProviderUnavailableError
from app.news.providers.factory import create_news_provider

from .models import (
    AdminAuditLog,
    AdminAuditLogListResponse,
    AdminDataQuality,
    AdminProviderStatus,
    AdminSystemHealth,
)


class AdminService:
    """Build authenticated operational views for administrators."""

    async def system_health(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> AdminSystemHealth:
        database = "healthy"
        try:
            await session.execute(text("SELECT 1"))
        except Exception:
            database = "unavailable"

        providers = (
            await self._market_provider_status(settings),
            self._news_provider_status(settings),
            AdminProviderStatus(
                name="llm",
                status="configured" if settings.llm_api_key else "unconfigured",
                detail=(
                    "LLM API key is configured."
                    if settings.llm_api_key
                    else "LLM API key is not configured."
                ),
            ),
            AdminProviderStatus(
                name="smtp",
                status=(
                    "configured"
                    if settings.smtp_host and settings.smtp_from_email
                    else "unconfigured"
                ),
                detail=(
                    "SMTP delivery is configured."
                    if settings.smtp_host and settings.smtp_from_email
                    else "SMTP delivery is not configured."
                ),
            ),
        )

        quality = await self._data_quality(session)
        audit_count = await session.scalar(
            select(func.count()).select_from(AdminAuditLogRecord),
        )

        return AdminSystemHealth(
            database=database,
            providers=providers,
            background_jobs="not_configured",
            data_quality=quality,
            audit_log_entries=int(audit_count or 0),
            checked_at=datetime.now(UTC),
        )

    async def record_audit(
        self,
        session: AsyncSession,
        *,
        actor_user_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        detail: dict[str, object] | None = None,
    ) -> AdminAuditLogRecord:
        record = AdminAuditLogRecord(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    async def list_audit_logs(
        self,
        session: AsyncSession,
        *,
        limit: int,
        offset: int,
    ) -> AdminAuditLogListResponse:
        total = int(
            await session.scalar(
                select(func.count()).select_from(AdminAuditLogRecord),
            )
            or 0,
        )
        result = await session.execute(
            select(AdminAuditLogRecord)
            .order_by(AdminAuditLogRecord.created_at.desc())
            .offset(offset)
            .limit(limit),
        )

        return AdminAuditLogListResponse(
            entries=tuple(self._audit_model(record) for record in result.scalars()),
            total=total,
        )

    async def _data_quality(self, session: AsyncSession) -> AdminDataQuality:
        models = (
            Instrument,
            MarketQuote,
            MarketBar,
            FundamentalSnapshot,
            NewsArticle,
            EventRecord,
            SignalRecord,
            RecommendationRecord,
            ModelMonitoringSnapshot,
        )
        counts = [
            int(await session.scalar(select(func.count()).select_from(model)) or 0)
            for model in models
        ]

        return AdminDataQuality(
            instruments=counts[0],
            market_quotes=counts[1],
            market_bars=counts[2],
            fundamentals=counts[3],
            news_articles=counts[4],
            events=counts[5],
            signals=counts[6],
            recommendations=counts[7],
            monitoring_snapshots=counts[8],
        )

    async def _market_provider_status(
        self,
        settings: Settings,
    ) -> AdminProviderStatus:
        if not settings.market_data_base_url:
            return AdminProviderStatus(
                name="market_data",
                status="unconfigured",
                detail="Market-data provider URL is not configured.",
            )

        try:
            health = await create_market_data_provider(settings).health_check()
        except MarketDataProviderError as exc:
            return AdminProviderStatus(
                name="market_data",
                status="unavailable",
                detail=str(exc),
            )

        return AdminProviderStatus(
            name="market_data",
            status=health.status,
            detail=health.detail or "Provider health check completed.",
        )

    @staticmethod
    def _news_provider_status(settings: Settings) -> AdminProviderStatus:
        try:
            create_news_provider(settings)
        except NewsProviderUnavailableError as exc:
            return AdminProviderStatus(
                name="news",
                status="unconfigured",
                detail=str(exc),
            )

        return AdminProviderStatus(
            name="news",
            status="configured",
            detail="News provider credentials are configured.",
        )

    @staticmethod
    def _audit_model(record: AdminAuditLogRecord) -> AdminAuditLog:
        return AdminAuditLog(
            id=record.id,
            actor_user_id=record.actor_user_id,
            action=record.action,
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            detail=record.detail,
            created_at=record.created_at,
        )

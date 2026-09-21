from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminAuditLog(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID
    actor_user_id: UUID | None
    action: str = Field(min_length=1, max_length=128)
    resource_type: str = Field(min_length=1, max_length=128)
    resource_id: str | None = Field(default=None, max_length=128)
    detail: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class AdminProviderStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    status: str
    detail: str


class AdminDataQuality(BaseModel):
    model_config = ConfigDict(frozen=True)
    instruments: int
    market_quotes: int
    market_bars: int
    fundamentals: int
    news_articles: int
    events: int
    signals: int
    recommendations: int
    monitoring_snapshots: int


class AdminSystemHealth(BaseModel):
    model_config = ConfigDict(frozen=True)
    database: str
    providers: tuple[AdminProviderStatus, ...]
    background_jobs: str
    data_quality: AdminDataQuality
    audit_log_entries: int
    checked_at: datetime


class AdminAuditLogListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    entries: tuple[AdminAuditLog, ...]
    total: int

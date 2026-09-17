from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class NewsSource(BaseModel):
    """Normalized metadata for a news publisher."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=255)


class NewsArticle(BaseModel):
    """Normalized news article."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    source_id: UUID
    source_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    source_domain: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    summary: str | None = None
    author: str | None = Field(default=None, max_length=255)
    published_at: datetime
    discovered_at: datetime
    content_hash: str = Field(min_length=32, max_length=128)
    language: str = Field(default="en", min_length=2, max_length=16)

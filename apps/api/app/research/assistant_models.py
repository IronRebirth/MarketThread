from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.research.models import ResearchSourceReference


class ResearchAnswerRequest(BaseModel):
    """Request for a grounded AI research answer."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1, max_length=2000)
    as_of: datetime | None = None
    limit: int = Field(default=8, ge=1, le=20)


class GeneratedResearchAnswer(BaseModel):
    """Structured model output before source-reference validation."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(min_length=1, max_length=12000)
    key_points: tuple[str, ...] = ()
    explanation: str = Field(min_length=1, max_length=8000)
    citation_ids: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


class ResearchAnswer(BaseModel):
    """Grounded research answer with validated MarketThread references."""

    model_config = ConfigDict(frozen=True)

    question: str
    as_of: datetime
    answer: str
    key_points: tuple[str, ...]
    explanation: str
    uncertainty: tuple[str, ...]
    citations: tuple[ResearchSourceReference, ...]
    model: str
    generated_at: datetime
    grounded: bool = True

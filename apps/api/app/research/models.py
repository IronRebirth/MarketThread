from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResearchQuery(BaseModel):
    """Normalized research question and retrieval controls."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1, max_length=2000)
    as_of: datetime
    limit: int = Field(default=8, ge=1, le=20)


class ResearchInstrument(BaseModel):
    """Instrument identified as relevant to a research question."""

    model_config = ConfigDict(frozen=True)

    instrument_id: UUID
    symbol: str
    name: str
    exchange: str
    currency: str


class ResearchArticle(BaseModel):
    """Persisted source article included in the research context."""

    model_config = ConfigDict(frozen=True)

    article_id: UUID
    source_name: str
    source_domain: str
    title: str
    url: str
    published_at: datetime


class ResearchEvent(BaseModel):
    """Persisted market event included in the research context."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    event_type: str
    title: str
    summary: str
    catalyst: str
    market_relevance: str
    impact_direction: str
    affected_entities: tuple[str, ...]
    affected_sectors: tuple[str, ...]
    source_article_ids: tuple[UUID, ...]
    first_seen_at: datetime
    confidence: float


class ResearchCompanyImpact(BaseModel):
    """Persisted company-impact assessment included in context."""

    model_config = ConfigDict(frozen=True)

    impact_id: UUID
    event_id: UUID
    company_name: str
    ticker: str | None
    impact_type: str
    direction: str
    mechanism: str
    confidence: float
    evidence_article_ids: tuple[UUID, ...]
    rationale: str


class ResearchMarketImpact(BaseModel):
    """Persisted economic transmission-path assessment."""

    model_config = ConfigDict(frozen=True)

    market_impact_id: UUID
    event_id: UUID
    company_name: str
    ticker: str | None
    impact_type: str
    direction: str
    factor: str
    time_horizon: str
    confidence: float
    evidence_article_ids: tuple[UUID, ...]
    rationale: str


class ResearchSignal(BaseModel):
    """Persisted market signal included in the research context."""

    model_config = ConfigDict(frozen=True)

    signal_id: UUID
    event_id: UUID
    instrument_id: UUID
    company_name: str
    ticker: str | None
    created_at: datetime
    direction: str
    strength: str
    opportunity: str
    confidence: float
    risk_score: float
    time_horizon: str
    supporting_factors: tuple[str, ...]
    contradicting_factors: tuple[str, ...]
    evidence_article_ids: tuple[UUID, ...]
    invalidation_conditions: tuple[str, ...]
    rationale: str


class ResearchRecommendation(BaseModel):
    """Persisted recommendation included in the research context."""

    model_config = ConfigDict(frozen=True)

    recommendation_id: UUID
    signal_id: UUID
    event_id: UUID
    company_name: str
    ticker: str | None
    created_at: datetime
    state: str
    signal_direction: str
    confidence_score: float
    risk_score: float
    confidence_level: str
    risk_level: str
    time_horizon: str
    supporting_factors: tuple[str, ...]
    contradicting_factors: tuple[str, ...]
    assumptions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    evidence_article_ids: tuple[UUID, ...]
    rationale: str


class ResearchFundamentals(BaseModel):
    """Persisted fundamental snapshot included in the research context."""

    model_config = ConfigDict(frozen=True)

    instrument_id: UUID
    period_end: date
    revenue_growth: str | None
    earnings_growth: str | None
    gross_margin: str | None
    operating_margin: str | None
    net_margin: str | None
    roe: str | None
    roic: str | None
    debt_to_equity: str | None
    debt_to_ebitda: str | None
    operating_cash_flow: str | None
    free_cash_flow: str | None
    pe_ratio: str | None
    ps_ratio: str | None
    ev_to_ebitda: str | None
    dividend_yield: str | None
    source: str


class ResearchPortfolioPosition(BaseModel):
    """Current user-owned portfolio position included in context."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    portfolio_name: str
    instrument_id: UUID
    symbol: str
    company_name: str
    quantity: str
    average_cost: str


class ResearchSourceReference(BaseModel):
    """Stable reference to one persisted MarketThread source record."""

    model_config = ConfigDict(frozen=True)

    reference_id: str
    source_type: str
    source_record_id: UUID
    observed_at: datetime | date
    title: str | None = None
    url: str | None = None


class ResearchContext(BaseModel):
    """Grounded context assembled only from persisted MarketThread records."""

    model_config = ConfigDict(frozen=True)

    query: ResearchQuery
    retrieval_started_at: datetime
    instruments: tuple[ResearchInstrument, ...]
    articles: tuple[ResearchArticle, ...]
    events: tuple[ResearchEvent, ...]
    company_impacts: tuple[ResearchCompanyImpact, ...]
    market_impacts: tuple[ResearchMarketImpact, ...]
    signals: tuple[ResearchSignal, ...]
    recommendations: tuple[ResearchRecommendation, ...]
    fundamentals: tuple[ResearchFundamentals, ...]
    portfolio_positions: tuple[ResearchPortfolioPosition, ...]
    source_references: tuple[ResearchSourceReference, ...]
    limitations: tuple[str, ...]

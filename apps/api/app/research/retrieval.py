from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord
from app.db.models.fundamental_snapshot import FundamentalSnapshot
from app.db.models.instrument import Instrument
from app.db.models.market_impact import MarketImpactRecord
from app.db.models.news import NewsArticle, NewsSource
from app.db.models.portfolio import PortfolioRecord
from app.db.models.recommendation import RecommendationRecord
from app.db.models.signal import SignalRecord
from app.research.models import (
    ResearchArticle,
    ResearchCompanyImpact,
    ResearchContext,
    ResearchEvent,
    ResearchFundamentals,
    ResearchInstrument,
    ResearchMarketImpact,
    ResearchPortfolioPosition,
    ResearchQuery,
    ResearchRecommendation,
    ResearchSignal,
    ResearchSourceReference,
)


class ResearchContextService:
    """Assemble timestamp-bounded, persisted research evidence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build(
        self,
        query: ResearchQuery,
        *,
        user_id: UUID,
    ) -> ResearchContext:
        retrieval_started_at = datetime.now(UTC)
        question = query.question.strip()

        if not question:
            raise ValueError("Research question must not be empty.")

        terms = tuple(
            term.lower()
            for term in question.replace(",", " ").split()
            if len(term) >= 2
        )

        instruments = await self._find_instruments(terms, query.limit)
        symbols = {item.symbol.upper() for item in instruments}

        articles = await self._find_articles(terms, query)
        article_ids = {item.article_id for item in articles}

        events = await self._find_events(
            terms,
            article_ids,
            symbols,
            query,
        )
        event_ids = {item.event_id for item in events}

        company_impacts = await self._find_company_impacts(
            event_ids,
            symbols,
            query,
        )
        market_impacts = await self._find_market_impacts(
            event_ids,
            symbols,
            query,
        )

        instrument_ids = {item.instrument_id for item in instruments}
        signals = await self._find_signals(
            instrument_ids,
            event_ids,
            query,
        )
        recommendations = await self._find_recommendations(
            signals,
            query,
        )
        fundamentals = await self._find_fundamentals(
            instrument_ids,
            query,
        )
        portfolio_positions = await self._find_portfolio_positions(
            user_id,
            instrument_ids,
            query.as_of,
        )

        references = self._build_references(
            articles,
            events,
            company_impacts,
            market_impacts,
            signals,
            recommendations,
            fundamentals,
            query.as_of,
        )

        limitations: list[str] = []

        if not instruments:
            limitations.append(
                "No persisted instrument matched the research question.",
            )
        if not articles:
            limitations.append(
                "No persisted news articles matched within the as-of cutoff.",
            )
        if not events:
            limitations.append(
                "No persisted market events matched within the as-of cutoff.",
            )
        if not signals:
            limitations.append(
                "No persisted market signals matched within the as-of cutoff.",
            )

        return ResearchContext(
            query=query,
            retrieval_started_at=retrieval_started_at,
            instruments=tuple(instruments),
            articles=tuple(articles),
            events=tuple(events),
            company_impacts=tuple(company_impacts),
            market_impacts=tuple(market_impacts),
            signals=tuple(signals),
            recommendations=tuple(recommendations),
            fundamentals=tuple(fundamentals),
            portfolio_positions=tuple(portfolio_positions),
            source_references=tuple(references),
            limitations=tuple(limitations),
        )

    async def _find_instruments(
        self,
        terms: tuple[str, ...],
        limit: int,
    ) -> list[ResearchInstrument]:
        statement = select(Instrument).where(Instrument.is_active.is_(True))

        if terms:
            statement = statement.where(
                or_(
                    *[
                        Instrument.symbol.ilike(f"%{term}%")
                        | Instrument.name.ilike(f"%{term}%")
                        for term in terms
                    ],
                ),
            )

        result = await self.session.execute(statement.limit(limit))
        records = result.scalars().all()

        return [
            ResearchInstrument(
                instrument_id=record.id,
                symbol=record.symbol,
                name=record.name,
                exchange=record.exchange,
                currency=record.currency,
            )
            for record in records
        ]

    async def _find_articles(
        self,
        terms: tuple[str, ...],
        query: ResearchQuery,
    ) -> list[ResearchArticle]:
        statement = (
            select(NewsArticle, NewsSource)
            .join(NewsSource, NewsSource.id == NewsArticle.source_id)
            .where(NewsArticle.published_at <= query.as_of)
            .order_by(NewsArticle.published_at.desc())
            .limit(query.limit)
        )

        if terms:
            pattern = "%" + " ".join(terms[:3]) + "%"
            statement = statement.where(
                NewsArticle.title.ilike(pattern)
                | NewsArticle.summary.ilike(pattern),
            )

        result = await self.session.execute(statement)

        return [
            ResearchArticle(
                article_id=record.id,
                source_name=source.name,
                source_domain=source.domain,
                title=record.title,
                url=record.url,
                published_at=record.published_at,
            )
            for record, source in result.all()
        ]

    async def _find_events(
        self,
        terms: tuple[str, ...],
        article_ids: set[UUID],
        symbols: set[str],
        query: ResearchQuery,
    ) -> list[ResearchEvent]:
        statement = (
            select(EventRecord)
            .where(EventRecord.first_seen_at <= query.as_of)
            .order_by(EventRecord.first_seen_at.desc())
            .limit(query.limit)
        )

        if article_ids:
            statement = statement.where(
                or_(
                    *[
                        cast(EventRecord.source_article_ids, JSONB).op("@>")(
                            [str(article_id)],
                        )
                        for article_id in article_ids
                    ],
                ),
            )
        elif symbols or terms:
            pattern = "%" + " ".join(terms[:3]) + "%"
            statement = statement.where(
                EventRecord.title.ilike(pattern)
                | EventRecord.summary.ilike(pattern),
            )

        result = await self.session.execute(statement)

        return [
            ResearchEvent(
                event_id=record.id,
                event_type=record.event_type,
                title=record.title,
                summary=record.summary,
                catalyst=record.catalyst,
                market_relevance=record.market_relevance,
                impact_direction=record.impact_direction,
                affected_entities=tuple(record.affected_entities),
                affected_sectors=tuple(record.affected_sectors),
                source_article_ids=tuple(
                    UUID(value) for value in record.source_article_ids
                ),
                first_seen_at=record.first_seen_at,
                confidence=record.confidence,
            )
            for record in result.scalars().all()
        ]

    async def _find_company_impacts(
        self,
        event_ids: set[UUID],
        symbols: set[str],
        query: ResearchQuery,
    ) -> list[ResearchCompanyImpact]:
        if not event_ids:
            return []

        statement = (
            select(CompanyImpactRecord)
            .join(EventRecord, EventRecord.id == CompanyImpactRecord.event_id)
            .where(
                CompanyImpactRecord.event_id.in_(event_ids),
                EventRecord.first_seen_at <= query.as_of,
            )
            .limit(query.limit)
        )

        if symbols:
            statement = statement.where(
                CompanyImpactRecord.ticker.in_(symbols),
            )

        result = await self.session.execute(statement)

        return [
            ResearchCompanyImpact(
                impact_id=record.id,
                event_id=record.event_id,
                company_name=record.company_name,
                ticker=record.ticker,
                impact_type=record.impact_type,
                direction=record.direction,
                mechanism=record.mechanism,
                confidence=record.confidence,
                evidence_article_ids=tuple(
                    UUID(value) for value in record.evidence_article_ids
                ),
                rationale=record.rationale,
            )
            for record in result.scalars().all()
        ]

    async def _find_market_impacts(
        self,
        event_ids: set[UUID],
        symbols: set[str],
        query: ResearchQuery,
    ) -> list[ResearchMarketImpact]:
        if not event_ids:
            return []

        statement = (
            select(MarketImpactRecord)
            .join(EventRecord, EventRecord.id == MarketImpactRecord.event_id)
            .where(
                MarketImpactRecord.event_id.in_(event_ids),
                EventRecord.first_seen_at <= query.as_of,
            )
            .limit(query.limit)
        )

        if symbols:
            statement = statement.where(
                MarketImpactRecord.ticker.in_(symbols),
            )

        result = await self.session.execute(statement)

        return [
            ResearchMarketImpact(
                market_impact_id=record.id,
                event_id=record.event_id,
                company_name=record.company_name,
                ticker=record.ticker,
                impact_type=record.impact_type,
                direction=record.direction,
                factor=record.factor,
                time_horizon=record.time_horizon,
                confidence=record.confidence,
                evidence_article_ids=tuple(
                    UUID(value) for value in record.evidence_article_ids
                ),
                rationale=record.rationale,
            )
            for record in result.scalars().all()
        ]

    async def _find_signals(
        self,
        instrument_ids: set[UUID],
        event_ids: set[UUID],
        query: ResearchQuery,
    ) -> list[ResearchSignal]:
        if not instrument_ids and not event_ids:
            return []

        statement = select(SignalRecord).where(
            SignalRecord.created_at <= query.as_of,
        )

        if instrument_ids:
            statement = statement.where(
                SignalRecord.instrument_id.in_(instrument_ids),
            )
        else:
            statement = statement.where(SignalRecord.event_id.in_(event_ids))

        statement = statement.order_by(
            SignalRecord.created_at.desc(),
        ).limit(query.limit)

        result = await self.session.execute(statement)

        return [
            ResearchSignal(
                signal_id=record.id,
                event_id=record.event_id,
                instrument_id=record.instrument_id,
                company_name=record.company_name,
                ticker=record.ticker,
                created_at=record.created_at,
                direction=record.direction,
                strength=record.strength,
                opportunity=record.opportunity,
                confidence=record.confidence,
                risk_score=record.risk_score,
                time_horizon=record.time_horizon,
                supporting_factors=tuple(record.supporting_factors),
                contradicting_factors=tuple(record.contradicting_factors),
                evidence_article_ids=tuple(
                    UUID(value) for value in record.evidence_article_ids
                ),
                invalidation_conditions=tuple(record.invalidation_conditions),
                rationale=record.rationale,
            )
            for record in result.scalars().all()
        ]

    async def _find_recommendations(
        self,
        signals: list[ResearchSignal],
        query: ResearchQuery,
    ) -> list[ResearchRecommendation]:
        signal_ids = {item.signal_id for item in signals}
        if not signal_ids:
            return []

        statement = (
            select(RecommendationRecord)
            .where(
                RecommendationRecord.signal_id.in_(signal_ids),
                RecommendationRecord.created_at <= query.as_of,
            )
            .order_by(
                RecommendationRecord.created_at.desc(),
            )
            .limit(query.limit)
        )

        result = await self.session.execute(statement)

        return [
            ResearchRecommendation(
                recommendation_id=record.id,
                signal_id=record.signal_id,
                event_id=record.event_id,
                company_name=record.company_name,
                ticker=record.ticker,
                created_at=record.created_at,
                state=record.state,
                signal_direction=record.signal_direction,
                confidence_score=record.confidence_score,
                risk_score=record.risk_score,
                confidence_level=record.confidence_level,
                risk_level=record.risk_level,
                time_horizon=record.time_horizon,
                supporting_factors=tuple(record.supporting_factors),
                contradicting_factors=tuple(record.contradicting_factors),
                assumptions=tuple(record.assumptions),
                invalidation_conditions=tuple(record.invalidation_conditions),
                evidence_article_ids=tuple(
                    UUID(value) for value in record.evidence_article_ids
                ),
                rationale=record.rationale,
            )
            for record in result.scalars().all()
        ]

    async def _find_fundamentals(
        self,
        instrument_ids: set[UUID],
        query: ResearchQuery,
    ) -> list[ResearchFundamentals]:
        if not instrument_ids:
            return []

        result = await self.session.execute(
            select(FundamentalSnapshot)
            .where(
                FundamentalSnapshot.instrument_id.in_(instrument_ids),
                FundamentalSnapshot.period_end <= query.as_of.date(),
            )
            .order_by(
                FundamentalSnapshot.period_end.desc(),
            )
            .limit(query.limit),
        )

        return [
            ResearchFundamentals(
                instrument_id=record.instrument_id,
                period_end=record.period_end,
                revenue_growth=str(record.revenue_growth)
                if record.revenue_growth is not None
                else None,
                earnings_growth=str(record.earnings_growth)
                if record.earnings_growth is not None
                else None,
                gross_margin=str(record.gross_margin)
                if record.gross_margin is not None
                else None,
                operating_margin=str(record.operating_margin)
                if record.operating_margin is not None
                else None,
                net_margin=str(record.net_margin)
                if record.net_margin is not None
                else None,
                roe=str(record.roe) if record.roe is not None else None,
                roic=str(record.roic) if record.roic is not None else None,
                debt_to_equity=str(record.debt_to_equity)
                if record.debt_to_equity is not None
                else None,
                debt_to_ebitda=str(record.debt_to_ebitda)
                if record.debt_to_ebitda is not None
                else None,
                operating_cash_flow=str(record.operating_cash_flow)
                if record.operating_cash_flow is not None
                else None,
                free_cash_flow=str(record.free_cash_flow)
                if record.free_cash_flow is not None
                else None,
                pe_ratio=str(record.pe_ratio)
                if record.pe_ratio is not None
                else None,
                ps_ratio=str(record.ps_ratio)
                if record.ps_ratio is not None
                else None,
                ev_to_ebitda=str(record.ev_to_ebitda)
                if record.ev_to_ebitda is not None
                else None,
                dividend_yield=str(record.dividend_yield)
                if record.dividend_yield is not None
                else None,
                source=record.source,
            )
            for record in result.scalars().all()
        ]

    async def _find_portfolio_positions(
        self,
        user_id: UUID,
        instrument_ids: set[UUID],
        as_of: datetime,
    ) -> list[ResearchPortfolioPosition]:
        if not instrument_ids:
            return []

        # The current position table has no effective timestamp. Use the
        # persisted position history instead so point-in-time research does not
        # silently expose a later portfolio state.
        from app.db.models.portfolio_history import PortfolioPositionHistoryRecord

        latest_rank = (
            func.row_number()
            .over(
                partition_by=(
                    PortfolioPositionHistoryRecord.portfolio_id,
                    PortfolioPositionHistoryRecord.instrument_id,
                ),
                order_by=(
                    PortfolioPositionHistoryRecord.recorded_at.desc(),
                    PortfolioPositionHistoryRecord.sequence_id.desc(),
                ),
            )
            .label("history_rank")
        )

        latest_history = (
            select(
                PortfolioPositionHistoryRecord.sequence_id.label("sequence_id"),
                latest_rank,
            )
            .join(
                PortfolioRecord,
                PortfolioRecord.id == PortfolioPositionHistoryRecord.portfolio_id,
            )
            .where(
                PortfolioRecord.user_id == user_id,
                PortfolioPositionHistoryRecord.instrument_id.in_(instrument_ids),
                PortfolioPositionHistoryRecord.recorded_at <= as_of,
            )
            .subquery()
        )

        result = await self.session.execute(
            select(
                PortfolioRecord,
                PortfolioPositionHistoryRecord,
                Instrument,
            )
            .join(
                PortfolioPositionHistoryRecord,
                PortfolioPositionHistoryRecord.portfolio_id == PortfolioRecord.id,
            )
            .join(
                Instrument,
                Instrument.id == PortfolioPositionHistoryRecord.instrument_id,
            )
            .join(
                latest_history,
                latest_history.c.sequence_id
                == PortfolioPositionHistoryRecord.sequence_id,
            )
            .where(
                PortfolioRecord.user_id == user_id,
                latest_history.c.history_rank == 1,
                PortfolioPositionHistoryRecord.quantity > 0,
            ),
        )

        return [
            ResearchPortfolioPosition(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio.name,
                instrument_id=position.instrument_id,
                symbol=instrument.symbol,
                company_name=instrument.name,
                quantity=str(position.quantity),
                average_cost=str(position.average_cost),
            )
            for portfolio, position, instrument in result.all()
        ]

    @staticmethod
    def _build_references(
        articles,
        events,
        company_impacts,
        market_impacts,
        signals,
        recommendations,
        fundamentals,
        query_as_of: datetime,
    ):
        references: list[ResearchSourceReference] = []

        for article in articles:
            references.append(
                ResearchSourceReference(
                    reference_id=f"article:{article.article_id}",
                    source_type="news_article",
                    source_record_id=article.article_id,
                    observed_at=article.published_at,
                    title=article.title,
                    url=article.url,
                ),
            )

        for event in events:
            references.append(
                ResearchSourceReference(
                    reference_id=f"event:{event.event_id}",
                    source_type="market_event",
                    source_record_id=event.event_id,
                    observed_at=event.first_seen_at,
                    title=event.title,
                ),
            )

        event_times = {event.event_id: event.first_seen_at for event in events}

        for impact in company_impacts:
            references.append(
                ResearchSourceReference(
                    reference_id=f"company-impact:{impact.impact_id}",
                    source_type="company_impact",
                    source_record_id=impact.impact_id,
                    observed_at=event_times.get(impact.event_id, query_as_of),
                    title=impact.company_name,
                ),
            )

        for impact in market_impacts:
            references.append(
                ResearchSourceReference(
                    reference_id=f"market-impact:{impact.market_impact_id}",
                    source_type="market_impact",
                    source_record_id=impact.market_impact_id,
                    observed_at=event_times.get(impact.event_id, query_as_of),
                    title=impact.company_name,
                ),
            )

        for signal in signals:
            references.append(
                ResearchSourceReference(
                    reference_id=f"signal:{signal.signal_id}",
                    source_type="market_signal",
                    source_record_id=signal.signal_id,
                    observed_at=signal.created_at,
                    title=signal.company_name,
                ),
            )

        for recommendation in recommendations:
            references.append(
                ResearchSourceReference(
                    reference_id=f"recommendation:{recommendation.recommendation_id}",
                    source_type="recommendation",
                    source_record_id=recommendation.recommendation_id,
                    observed_at=recommendation.created_at,
                    title=recommendation.company_name,
                ),
            )

        for fundamental in fundamentals:
            references.append(
                ResearchSourceReference(
                    reference_id=f"fundamentals:{fundamental.instrument_id}:{fundamental.period_end}",
                    source_type="fundamentals",
                    source_record_id=fundamental.instrument_id,
                    observed_at=fundamental.period_end,
                    title=str(fundamental.period_end),
                ),
            )

        return references

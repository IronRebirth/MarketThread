from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select

from app.company_impact.models import CompanyImpactDirection, ImpactType
from app.db.models.event import EventRecord
from app.db.models.instrument import Instrument
from app.db.models.market_impact import MarketImpactRecord
from app.market_impact.models import ImpactFactor, TimeHorizon
from app.portfolio.event_sensitivity_models import (
    PortfolioEventSensitivity,
    PortfolioEventSensitivityItem,
)
from app.portfolio.models import Portfolio, PortfolioPosition
from app.portfolio.persistence import PortfolioPersistenceService


class PortfolioEventSensitivityService:
    """Build read-only event sensitivity from persisted portfolio intelligence."""

    def __init__(
        self,
        persistence: PortfolioPersistenceService,
    ) -> None:
        self.persistence = persistence

    async def build(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        assessed_at: datetime | None = None,
        limit: int = 100,
    ) -> PortfolioEventSensitivity:
        """Build event sensitivity for a user-owned portfolio."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        assessment_time = assessed_at or datetime.now(UTC)

        self._validate_aware_datetime(
            assessment_time,
            "assessed_at",
        )

        assessment_time = assessment_time.astimezone(UTC)

        detail = await self.persistence.get_detail_for_user(
            user_id,
            portfolio_id,
        )

        if detail is None:
            raise ValueError("Portfolio not found.")

        portfolio_record, position_count, position_records = detail

        portfolio = Portfolio(
            portfolio_id=portfolio_record.id,
            name=portfolio_record.name,
            created_at=portfolio_record.created_at,
            updated_at=portfolio_record.updated_at,
            position_count=position_count,
        )

        positions = await self._load_positions(
            position_records,
        )

        if not positions:
            return PortfolioEventSensitivity(
                portfolio=portfolio,
                assessed_at=assessment_time,
                position_count=0,
                matched_position_count=0,
                unmatched_position_count=0,
                event_count=0,
                impact_count=0,
                returned_impact_count=0,
                quality="empty",
                unmatched_symbols=(),
                methodology=self._methodology(),
                notes=(
                    "The portfolio has no current positions.",
                    "No event sensitivity can be assessed without current holdings.",
                ),
                items=(),
            )

        symbol_positions: dict[str, list[PortfolioPosition]] = defaultdict(list)

        for position in positions:
            normalized_symbol = self._normalize_symbol(
                position.symbol,
            )

            if normalized_symbol:
                symbol_positions[normalized_symbol].append(position)

        ambiguous_symbols = {
            symbol
            for symbol, symbol_position_list in symbol_positions.items()
            if len(symbol_position_list) > 1
        }

        matchable_symbols = tuple(
            sorted(
                symbol for symbol in symbol_positions if symbol not in ambiguous_symbols
            ),
        )

        if not matchable_symbols:
            unmatched_symbols = tuple(
                sorted(symbol_positions),
            )

            notes: list[str] = [
                "No portfolio positions were eligible for exact ticker matching.",
            ]

            if ambiguous_symbols:
                notes.append(
                    "Some portfolio symbols are ambiguous because multiple "
                    "instruments in the portfolio share the same normalized ticker.",
                )

            return PortfolioEventSensitivity(
                portfolio=portfolio,
                assessed_at=assessment_time,
                position_count=position_count,
                matched_position_count=0,
                unmatched_position_count=position_count,
                event_count=0,
                impact_count=0,
                returned_impact_count=0,
                quality="none",
                unmatched_symbols=unmatched_symbols,
                methodology=self._methodology(),
                notes=tuple(notes),
                items=(),
            )

        normalized_ticker = func.upper(
            func.trim(MarketImpactRecord.ticker),
        )

        matching_filter = normalized_ticker.in_(
            matchable_symbols,
        )

        impact_count = int(
            await self.persistence.session.scalar(
                select(
                    func.count(
                        MarketImpactRecord.id,
                    ),
                ).where(
                    matching_filter,
                ),
            )
            or 0
        )

        event_count = int(
            await self.persistence.session.scalar(
                select(
                    func.count(
                        func.distinct(
                            MarketImpactRecord.event_id,
                        ),
                    ),
                ).where(
                    matching_filter,
                ),
            )
            or 0
        )

        matched_symbols = set()

        if impact_count > 0:
            matched_symbol_rows = await self.persistence.session.execute(
                select(
                    normalized_ticker,
                )
                .where(
                    matching_filter,
                )
                .distinct(),
            )

            matched_symbols = {
                symbol for (symbol,) in matched_symbol_rows.all() if symbol is not None
            }

        matched_position_count = sum(
            1 for symbol in matchable_symbols if symbol in matched_symbols
        )

        unmatched_symbol_set = set(symbol_positions) - matched_symbols

        unmatched_symbols = tuple(
            sorted(unmatched_symbol_set),
        )

        statement = (
            select(
                MarketImpactRecord,
                EventRecord,
            )
            .join(
                EventRecord,
                EventRecord.id == MarketImpactRecord.event_id,
            )
            .where(
                matching_filter,
            )
            .order_by(
                EventRecord.first_seen_at.desc(),
                EventRecord.last_seen_at.desc(),
                MarketImpactRecord.id.desc(),
            )
            .limit(limit)
        )

        result = await self.persistence.session.execute(
            statement,
        )

        impact_rows: Sequence[tuple[MarketImpactRecord, EventRecord]] = result.all()

        items: list[PortfolioEventSensitivityItem] = []

        for market_impact_record, event_record in impact_rows:
            normalized_record_ticker = self._normalize_symbol(
                market_impact_record.ticker,
            )

            position_candidates = symbol_positions.get(
                normalized_record_ticker,
                [],
            )

            if len(position_candidates) != 1:
                continue

            items.append(
                self._to_item(
                    position=position_candidates[0],
                    market_impact_record=market_impact_record,
                    event_record=event_record,
                ),
            )

        unmatched_position_count = position_count - matched_position_count

        if position_count == 0:
            quality = "empty"
        elif impact_count == 0:
            quality = "none"
        elif unmatched_position_count > 0:
            quality = "partial"
        else:
            quality = "sufficient"

        notes = self._build_notes(
            position_count=position_count,
            ambiguous_symbols=ambiguous_symbols,
            impact_count=impact_count,
            returned_impact_count=len(items),
            limit=limit,
        )

        return PortfolioEventSensitivity(
            portfolio=portfolio,
            assessed_at=assessment_time,
            position_count=position_count,
            matched_position_count=matched_position_count,
            unmatched_position_count=unmatched_position_count,
            event_count=event_count,
            impact_count=impact_count,
            returned_impact_count=len(items),
            quality=quality,
            unmatched_symbols=unmatched_symbols,
            methodology=self._methodology(),
            notes=tuple(notes),
            items=tuple(items),
        )

    async def _load_positions(
        self,
        position_records,
    ) -> tuple[PortfolioPosition, ...]:
        """Resolve persisted positions to domain positions with instrument metadata."""

        positions: list[PortfolioPosition] = []

        for position_record in position_records:
            instrument = await self.persistence.session.get(
                Instrument,
                position_record.instrument_id,
            )

            if instrument is None:
                raise RuntimeError(
                    "Portfolio position references a missing instrument.",
                )

            positions.append(
                PortfolioPosition(
                    position_id=position_record.id,
                    portfolio_id=position_record.portfolio_id,
                    instrument_id=position_record.instrument_id,
                    quantity=position_record.quantity,
                    average_cost=position_record.average_cost,
                    created_at=position_record.created_at,
                    updated_at=position_record.updated_at,
                    symbol=instrument.symbol,
                    name=instrument.name,
                    exchange=instrument.exchange,
                    asset_class=instrument.asset_class,
                    currency=instrument.currency,
                    is_active=instrument.is_active,
                ),
            )

        return tuple(positions)

    @staticmethod
    def _to_item(
        *,
        position: PortfolioPosition,
        market_impact_record: MarketImpactRecord,
        event_record: EventRecord,
    ) -> PortfolioEventSensitivityItem:
        """Convert persisted event and market-impact records into a sensitivity item."""

        source_article_ids = tuple(
            UUID(article_id) for article_id in market_impact_record.evidence_article_ids
        )

        return PortfolioEventSensitivityItem(
            position=position,
            market_impact_id=market_impact_record.id,
            company_impact_id=market_impact_record.company_impact_id,
            event_id=event_record.id,
            company_name=market_impact_record.company_name,
            ticker=(
                market_impact_record.ticker.strip()
                if market_impact_record.ticker is not None
                else ""
            ),
            impact_type=ImpactType(
                market_impact_record.impact_type,
            ),
            direction=CompanyImpactDirection(
                market_impact_record.direction,
            ),
            factor=ImpactFactor(
                market_impact_record.factor,
            ),
            time_horizon=TimeHorizon(
                market_impact_record.time_horizon,
            ),
            confidence=market_impact_record.confidence,
            event_type=event_record.event_type,
            title=event_record.title,
            summary=event_record.summary,
            catalyst=event_record.catalyst,
            market_relevance=event_record.market_relevance,
            event_impact_direction=event_record.impact_direction,
            affected_entities=tuple(
                event_record.affected_entities,
            ),
            affected_sectors=tuple(
                event_record.affected_sectors,
            ),
            first_seen_at=event_record.first_seen_at,
            last_seen_at=event_record.last_seen_at,
            event_confidence=event_record.confidence,
            source_article_ids=source_article_ids,
            rationale=market_impact_record.rationale,
        )

    @staticmethod
    def _normalize_symbol(
        symbol: str | None,
    ) -> str:
        """Normalize a ticker for exact case-insensitive matching."""

        if symbol is None:
            return ""

        return symbol.strip().upper()

    @staticmethod
    def _build_notes(
        *,
        position_count: int,
        ambiguous_symbols: set[str],
        impact_count: int,
        returned_impact_count: int,
        limit: int,
    ) -> list[str]:
        """Build transparent methodology and coverage notes."""

        notes = [
            (
                "Matching uses exact normalized portfolio tickers "
                "(trimmed and case-insensitive); company names are not used "
                "for matching."
            ),
            (
                "Event sensitivity reports persisted Event, Company Impact, "
                "and Market Impact evidence; it does not forecast returns "
                "or calculate a numerical event-risk score."
            ),
            (
                "A single portfolio position may have multiple persisted "
                "market-impact records because different events or impact "
                "assessments can affect the same ticker."
            ),
        ]

        if ambiguous_symbols:
            notes.append(
                "Ambiguous portfolio symbols are not matched because multiple "
                "instruments share the same normalized ticker."
            )

        if impact_count > returned_impact_count:
            notes.append(
                (
                    f"The result list is limited to the first {limit} matching "
                    "impact records."
                ),
            )

        if impact_count == 0 and position_count > 0:
            notes.append(
                (
                    "No persisted market-impact records matched the current "
                    "portfolio tickers."
                ),
            )

        return notes

    @staticmethod
    def _validate_aware_datetime(
        value: datetime,
        label: str,
    ) -> None:
        """Require a timezone-aware datetime."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                f"{label} must be timezone-aware",
            )

    @staticmethod
    def _methodology() -> str:
        """Describe the event-sensitivity methodology."""

        return (
            "Read-only portfolio event sensitivity using current persisted "
            "positions matched to persisted Market Impact records by exact "
            "normalized ticker. Market Impact records are joined to their "
            "persisted events so the response preserves event context, "
            "company-impact linkage, evidence, confidence, impact factor, "
            "and time horizon. Confidence reflects evidence strength and "
            "does not represent probability of a future return. No numerical "
            "event-risk score or return forecast is generated."
        )

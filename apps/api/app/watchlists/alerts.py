from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import EventRecord
from app.db.models.instrument import Instrument
from app.db.models.market_impact import MarketImpactRecord
from app.db.models.watchlist import WatchlistItemRecord, WatchlistRecord
from app.watchlists.alerts_models import WatchlistAlert, WatchlistAlerts


class WatchlistAlertService:
    """Build deterministic, evidence-backed alerts for a user watchlist."""

    _ALERT_NAMESPACE = UUID(
        "4e5cc0e5-6b7f-4d5c-9ad8-93f6c7b7c5f1",
    )

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def build(
        self,
        user_id: UUID,
        watchlist_id: UUID,
        *,
        assessed_at: datetime | None = None,
        limit: int = 100,
    ) -> WatchlistAlerts:
        """Return new persisted intelligence relevant to watched instruments."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        assessment_time = assessed_at or datetime.now(UTC)

        self._validate_aware_datetime(
            assessment_time,
        )

        assessment_time = assessment_time.astimezone(UTC)

        watchlist_exists = await self.session.scalar(
            select(WatchlistRecord.id).where(
                WatchlistRecord.id == watchlist_id,
                WatchlistRecord.user_id == user_id,
            ),
        )

        if watchlist_exists is None:
            raise ValueError("Watchlist not found.")

        item_result = await self.session.execute(
            select(
                WatchlistItemRecord,
                Instrument.symbol,
            )
            .join(
                Instrument,
                Instrument.id == WatchlistItemRecord.instrument_id,
            )
            .where(
                WatchlistItemRecord.watchlist_id == watchlist_id,
            )
            .order_by(
                WatchlistItemRecord.added_at,
                WatchlistItemRecord.id,
            ),
        )

        item_rows = tuple(item_result.all())

        item_count = len(item_rows)

        if item_count == 0:
            return WatchlistAlerts(
                watchlist_id=watchlist_id,
                assessed_at=assessment_time,
                item_count=0,
                matched_item_count=0,
                unmatched_item_count=0,
                alert_count=0,
                returned_alert_count=0,
                quality="empty",
                alerts=(),
                methodology=self._methodology(),
                notes=(
                    "The watchlist has no tracked instruments.",
                    "No intelligence alerts can be assessed without watchlist items.",
                ),
            )

        item_symbols = {
            item_record.id: self._normalize_ticker(symbol)
            for item_record, symbol in item_rows
        }

        matchable_symbols = tuple(
            sorted(
                {symbol for symbol in item_symbols.values() if symbol},
            ),
        )

        if not matchable_symbols:
            return WatchlistAlerts(
                watchlist_id=watchlist_id,
                assessed_at=assessment_time,
                item_count=item_count,
                matched_item_count=0,
                unmatched_item_count=item_count,
                alert_count=0,
                returned_alert_count=0,
                quality="none",
                alerts=(),
                methodology=self._methodology(),
                notes=(
                    "No watchlist items had a usable ticker for exact "
                    "intelligence matching.",
                ),
            )

        normalized_market_impact_ticker = func.upper(
            func.trim(MarketImpactRecord.ticker),
        )
        normalized_instrument_symbol = func.upper(
            func.trim(Instrument.symbol),
        )

        statement = (
            select(
                WatchlistItemRecord,
                MarketImpactRecord,
                EventRecord,
            )
            .join(
                WatchlistRecord,
                WatchlistRecord.id == WatchlistItemRecord.watchlist_id,
            )
            .join(
                Instrument,
                Instrument.id == WatchlistItemRecord.instrument_id,
            )
            .join(
                MarketImpactRecord,
                normalized_market_impact_ticker == normalized_instrument_symbol,
            )
            .join(
                EventRecord,
                EventRecord.id == MarketImpactRecord.event_id,
            )
            .where(
                WatchlistRecord.id == watchlist_id,
                WatchlistRecord.user_id == user_id,
                normalized_market_impact_ticker.in_(matchable_symbols),
                EventRecord.first_seen_at >= WatchlistItemRecord.added_at,
                EventRecord.first_seen_at < assessment_time,
            )
            .order_by(
                EventRecord.first_seen_at.desc(),
                EventRecord.last_seen_at.desc(),
                MarketImpactRecord.id.desc(),
            )
        )

        result = await self.session.execute(statement)

        rows: Sequence[
            tuple[
                WatchlistItemRecord,
                MarketImpactRecord,
                EventRecord,
            ]
        ] = result.all()

        all_alert_rows: list[
            tuple[
                WatchlistItemRecord,
                MarketImpactRecord,
                EventRecord,
            ]
        ] = []

        for item_record, market_impact_record, event_record in rows:
            watchlist_symbol = item_symbols.get(
                item_record.id,
                "",
            )

            market_impact_symbol = self._normalize_ticker(
                market_impact_record.ticker,
            )

            if watchlist_symbol != market_impact_symbol:
                continue

            all_alert_rows.append(
                (
                    item_record,
                    market_impact_record,
                    event_record,
                ),
            )

        matched_item_ids = {item_record.id for item_record, _, _ in all_alert_rows}

        matched_item_count = len(matched_item_ids)
        unmatched_item_count = item_count - matched_item_count

        alert_count = len(all_alert_rows)

        limited_rows = all_alert_rows[:limit]

        alerts = tuple(
            self._to_alert(
                watchlist_id=watchlist_id,
                item_record=item_record,
                market_impact_record=market_impact_record,
                event_record=event_record,
            )
            for item_record, market_impact_record, event_record in limited_rows
        )

        if alert_count == 0:
            quality = "none"
        elif unmatched_item_count > 0:
            quality = "partial"
        else:
            quality = "sufficient"

        notes = [
            (
                "Alerts use exact normalized ticker matching: symbols and "
                "persisted market-impact tickers are trimmed and compared "
                "case-insensitively."
            ),
            (
                "An alert is eligible only when the related event was first "
                "observed on or after the watchlist item was added."
            ),
            (
                "Alerts are derived from persisted Market Impact and Event "
                "records; no new prediction or notification claim is created."
            ),
            (
                "Each alert has a deterministic identifier derived from the "
                "watchlist item and persisted market-impact record."
            ),
            (
                "Repeated retrieval of the same persisted intelligence "
                "therefore returns the same alert identity instead of "
                "creating duplicates."
            ),
        ]

        if unmatched_item_count > 0:
            notes.append(
                (
                    f"{unmatched_item_count} watchlist item(s) currently "
                    "have no matching eligible intelligence alert."
                ),
            )

        if alert_count > len(alerts):
            notes.append(
                (
                    f"Only the first {limit} alerts are returned; total "
                    f"eligible alert count is {alert_count}."
                ),
            )

        return WatchlistAlerts(
            watchlist_id=watchlist_id,
            assessed_at=assessment_time,
            item_count=item_count,
            matched_item_count=matched_item_count,
            unmatched_item_count=unmatched_item_count,
            alert_count=alert_count,
            returned_alert_count=len(alerts),
            quality=quality,
            alerts=alerts,
            methodology=self._methodology(),
            notes=tuple(notes),
        )

    @classmethod
    def _to_alert(
        cls,
        *,
        watchlist_id: UUID,
        item_record: WatchlistItemRecord,
        market_impact_record: MarketImpactRecord,
        event_record: EventRecord,
    ) -> WatchlistAlert:
        """Convert persisted intelligence into a deterministic alert."""

        symbol = cls._normalize_ticker(
            market_impact_record.ticker,
        )

        source_article_ids = tuple(
            UUID(article_id) for article_id in market_impact_record.evidence_article_ids
        )

        alert_id = uuid5(
            cls._ALERT_NAMESPACE,
            (f"{watchlist_id}:{item_record.id}:{market_impact_record.id}"),
        )

        explanation = cls._build_explanation(
            symbol=symbol,
            event_record=event_record,
            market_impact_record=market_impact_record,
        )

        return WatchlistAlert(
            alert_id=alert_id,
            watchlist_id=watchlist_id,
            watchlist_item_id=item_record.id,
            instrument_id=item_record.instrument_id,
            symbol=symbol,
            company_name=market_impact_record.company_name,
            ticker=symbol,
            market_impact_id=market_impact_record.id,
            company_impact_id=market_impact_record.company_impact_id,
            event_id=event_record.id,
            event_type=event_record.event_type,
            title=event_record.title,
            summary=event_record.summary,
            catalyst=event_record.catalyst,
            market_relevance=event_record.market_relevance,
            event_impact_direction=event_record.impact_direction,
            impact_type=market_impact_record.impact_type,
            direction=market_impact_record.direction,
            factor=market_impact_record.factor,
            time_horizon=market_impact_record.time_horizon,
            confidence=market_impact_record.confidence,
            event_confidence=event_record.confidence,
            watchlist_item_added_at=item_record.added_at,
            first_seen_at=event_record.first_seen_at,
            last_seen_at=event_record.last_seen_at,
            source_article_ids=source_article_ids,
            rationale=market_impact_record.rationale,
            explanation=explanation,
        )

    @staticmethod
    def _build_explanation(
        *,
        symbol: str,
        event_record: EventRecord,
        market_impact_record: MarketImpactRecord,
    ) -> str:
        """Build a descriptive alert explanation from persisted evidence."""

        return (
            f"{symbol} is on the watchlist and has persisted market-impact "
            f"intelligence linked to the event '{event_record.title}'. "
            f"The assessed impact is {market_impact_record.direction} via "
            f"{market_impact_record.factor} over a "
            f"{market_impact_record.time_horizon} horizon. The alert exposes "
            "the underlying event and evidence context; it does not predict "
            "a future return."
        )

    @staticmethod
    def _normalize_ticker(
        ticker: str | None,
    ) -> str:
        """Normalize a ticker for exact case-insensitive matching."""

        if ticker is None:
            return ""

        return ticker.strip().upper()

    @staticmethod
    def _validate_aware_datetime(
        value: datetime,
    ) -> None:
        """Require a timezone-aware assessment timestamp."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "assessed_at must be timezone-aware",
            )

    @staticmethod
    def _methodology() -> str:
        """Describe the watchlist-alert methodology."""

        return (
            "Watchlist alerts are derived read-only from current user-owned "
            "watchlist items and persisted Market Impact records joined to "
            "their persisted Events. Matching uses exact normalized ticker "
            "identity. An intelligence record is eligible only when the "
            "related event was first observed on or after the watchlist "
            "item was added. Each alert receives a deterministic UUID derived "
            "from its watchlist item and market-impact record, providing a "
            "stable identity without persisting duplicate alert rows. "
            "Alerts expose evidence and context and do not forecast returns "
            "or execute trades."
        )

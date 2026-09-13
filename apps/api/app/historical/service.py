from datetime import datetime
from uuid import UUID

from app.historical.analyzer import HistoricalEventAnalyzer
from app.historical.models import HistoricalEventAnalysis, HistoricalOutcome


class HistoricalEventAnalysisService:
    """Application service for historical event analysis."""

    def __init__(self) -> None:
        self._analyzer = HistoricalEventAnalyzer()

    def analyze(
        self,
        event_id: UUID,
        outcomes: tuple[HistoricalOutcome, ...],
        analyzed_at: datetime,
    ) -> HistoricalEventAnalysis:
        """Analyze observed market outcomes for an event."""

        return self._analyzer.analyze(
            event_id=event_id,
            outcomes=outcomes,
            analyzed_at=analyzed_at,
        )

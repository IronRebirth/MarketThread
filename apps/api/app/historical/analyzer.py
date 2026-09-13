from datetime import datetime
from uuid import UUID

from app.historical.models import (
    HistoricalEventAnalysis,
    HistoricalOutcome,
    OutcomeDirection,
)


class HistoricalEventAnalyzer:
    """Analyze observed outcomes without claiming causal attribution."""

    def analyze(
        self,
        event_id: UUID,
        outcomes: tuple[HistoricalOutcome, ...],
        analyzed_at: datetime,
    ) -> HistoricalEventAnalysis:
        """Summarize historical observations for an event."""

        notes = self._build_notes(outcomes)

        return HistoricalEventAnalysis(
            event_id=event_id,
            analyzed_at=analyzed_at,
            outcomes=outcomes,
            observation_count=len(outcomes),
            notes=notes,
        )

    @staticmethod
    def _build_notes(
        outcomes: tuple[HistoricalOutcome, ...],
    ) -> tuple[str, ...]:
        """Create observational notes from historical outcomes."""

        if not outcomes:
            return ("No historical market observations are available.",)

        available_returns = [
            outcome.return_pct for outcome in outcomes if outcome.return_pct is not None
        ]

        if not available_returns:
            return (
                "Historical price observations exist, but return data is unavailable.",
            )

        positive_count = sum(
            outcome.direction == OutcomeDirection.POSITIVE for outcome in outcomes
        )
        negative_count = sum(
            outcome.direction == OutcomeDirection.NEGATIVE for outcome in outcomes
        )

        notes = [
            (f"{len(available_returns)} historical return observations are available."),
        ]

        if positive_count > negative_count:
            notes.append(
                "More observed windows were positive than negative.",
            )
        elif negative_count > positive_count:
            notes.append(
                "More observed windows were negative than positive.",
            )
        else:
            notes.append(
                "Positive and negative observed windows were balanced.",
            )

        notes.append(
            "Observed movement does not establish that the event caused "
            "the market outcome.",
        )

        return tuple(notes)

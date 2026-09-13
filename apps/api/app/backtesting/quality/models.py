from enum import StrEnum


class BacktestQualityState(StrEnum):
    RELIABLE = "reliable"
    LIMITED_EVIDENCE = "limited_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class BacktestQualityWarning(StrEnum):
    LOW_SAMPLE_SIZE = "low_sample_size"
    NO_EVALUATIONS = "no_evaluations"
    LOW_COVERAGE = "low_coverage"


class BacktestQualityAssessment:
    def __init__(
        self,
        *,
        state: BacktestQualityState,
        evaluation_count: int,
        expected_count: int | None,
        coverage_ratio: float | None,
        minimum_evaluations: int,
        warnings: tuple[BacktestQualityWarning, ...],
        notes: tuple[str, ...],
    ) -> None:
        self.state = state
        self.evaluation_count = evaluation_count
        self.expected_count = expected_count
        self.coverage_ratio = coverage_ratio
        self.minimum_evaluations = minimum_evaluations
        self.warnings = warnings
        self.notes = notes

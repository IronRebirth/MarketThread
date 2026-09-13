from enum import StrEnum

from pydantic import BaseModel, Field


class BacktestQualityState(StrEnum):
    RELIABLE = "reliable"
    LIMITED_EVIDENCE = "limited_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class BacktestQualityWarning(StrEnum):
    LOW_SAMPLE_SIZE = "low_sample_size"
    NO_EVALUATIONS = "no_evaluations"
    LOW_COVERAGE = "low_coverage"


class BacktestQualityAssessment(BaseModel):
    state: BacktestQualityState
    evaluation_count: int
    expected_count: int | None
    coverage_ratio: float | None
    minimum_evaluations: int
    warnings: tuple[BacktestQualityWarning, ...] = Field(default_factory=tuple)
    notes: tuple[str, ...] = Field(default_factory=tuple)

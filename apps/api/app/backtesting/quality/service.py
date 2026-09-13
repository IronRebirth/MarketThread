from .analyzer import BacktestEvaluationQualityAnalyzer
from .models import BacktestQualityAssessment


class BacktestEvaluationQualityService:
    def __init__(
        self,
        analyzer: BacktestEvaluationQualityAnalyzer | None = None,
    ) -> None:
        self._analyzer = analyzer or BacktestEvaluationQualityAnalyzer()

    def assess(
        self,
        *,
        evaluation_count: int,
        expected_count: int | None = None,
        minimum_evaluations: int = 30,
        limited_evidence_threshold: int | None = None,
        minimum_coverage_ratio: float = 0.5,
    ) -> BacktestQualityAssessment:
        return self._analyzer.assess(
            evaluation_count=evaluation_count,
            expected_count=expected_count,
            minimum_evaluations=minimum_evaluations,
            limited_evidence_threshold=limited_evidence_threshold,
            minimum_coverage_ratio=minimum_coverage_ratio,
        )

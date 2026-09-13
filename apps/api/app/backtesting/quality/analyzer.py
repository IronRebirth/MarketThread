from .models import (
    BacktestQualityAssessment,
    BacktestQualityState,
    BacktestQualityWarning,
)


class BacktestEvaluationQualityAnalyzer:
    def assess(
        self,
        *,
        evaluation_count: int,
        expected_count: int | None = None,
        minimum_evaluations: int = 30,
        limited_evidence_threshold: int | None = None,
        minimum_coverage_ratio: float = 0.5,
    ) -> BacktestQualityAssessment:
        if evaluation_count < 0:
            raise ValueError("evaluation_count cannot be negative.")

        if expected_count is not None and expected_count < 0:
            raise ValueError("expected_count cannot be negative.")

        if minimum_evaluations < 1:
            raise ValueError("minimum_evaluations must be at least 1.")

        if limited_evidence_threshold is None:
            limited_evidence_threshold = minimum_evaluations * 2

        if limited_evidence_threshold < minimum_evaluations:
            raise ValueError(
                "limited_evidence_threshold must be greater than or equal "
                "to minimum_evaluations.",
            )

        if not 0.0 <= minimum_coverage_ratio <= 1.0:
            raise ValueError(
                "minimum_coverage_ratio must be between 0 and 1.",
            )

        coverage_ratio = None

        if expected_count is not None:
            if expected_count == 0:
                coverage_ratio = 1.0 if evaluation_count == 0 else 0.0
            else:
                coverage_ratio = min(
                    evaluation_count / expected_count,
                    1.0,
                )

        warnings: list[BacktestQualityWarning] = []
        notes: list[str] = []

        if evaluation_count == 0:
            state = BacktestQualityState.INSUFFICIENT_EVIDENCE
            warnings.append(BacktestQualityWarning.NO_EVALUATIONS)
            notes.append(
                "No backtest evaluations are available for quality assessment.",
            )
        elif evaluation_count < minimum_evaluations:
            state = BacktestQualityState.INSUFFICIENT_EVIDENCE
            warnings.append(BacktestQualityWarning.LOW_SAMPLE_SIZE)
            notes.append(
                "The evaluation sample is below the minimum threshold.",
            )
        elif evaluation_count < limited_evidence_threshold:
            state = BacktestQualityState.LIMITED_EVIDENCE
            warnings.append(BacktestQualityWarning.LOW_SAMPLE_SIZE)
            notes.append(
                "The evaluation sample is usable but remains limited.",
            )
        else:
            state = BacktestQualityState.RELIABLE
            notes.append(
                "The evaluation sample meets the minimum quality threshold.",
            )

        if coverage_ratio is not None and coverage_ratio < minimum_coverage_ratio:
            warnings.append(BacktestQualityWarning.LOW_COVERAGE)
            notes.append(
                "Evaluation coverage is below the configured minimum.",
            )

            if state == BacktestQualityState.RELIABLE:
                state = BacktestQualityState.LIMITED_EVIDENCE

        if expected_count is not None:
            notes.append(
                f"Evaluation coverage is "
                f"{coverage_ratio:.1%} of the expected evaluation set."
                if coverage_ratio is not None
                else "Evaluation coverage could not be calculated.",
            )

        return BacktestQualityAssessment(
            state=state,
            evaluation_count=evaluation_count,
            expected_count=expected_count,
            coverage_ratio=coverage_ratio,
            minimum_evaluations=minimum_evaluations,
            warnings=tuple(dict.fromkeys(warnings)),
            notes=tuple(notes),
        )

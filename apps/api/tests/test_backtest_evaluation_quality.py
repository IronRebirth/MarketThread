import pytest

from app.backtesting.quality import (
    BacktestEvaluationQualityService,
    BacktestQualityState,
    BacktestQualityWarning,
)


def test_zero_evaluations_are_insufficient_evidence() -> None:
    assessment = BacktestEvaluationQualityService().assess(
        evaluation_count=0,
    )

    assert assessment.state == BacktestQualityState.INSUFFICIENT_EVIDENCE
    assert assessment.evaluation_count == 0
    assert BacktestQualityWarning.NO_EVALUATIONS in assessment.warnings


def test_small_sample_is_insufficient_evidence() -> None:
    assessment = BacktestEvaluationQualityService().assess(
        evaluation_count=10,
        minimum_evaluations=30,
    )

    assert assessment.state == BacktestQualityState.INSUFFICIENT_EVIDENCE
    assert BacktestQualityWarning.LOW_SAMPLE_SIZE in assessment.warnings


def test_medium_sample_is_limited_evidence() -> None:
    assessment = BacktestEvaluationQualityService().assess(
        evaluation_count=40,
        minimum_evaluations=30,
        limited_evidence_threshold=60,
    )

    assert assessment.state == BacktestQualityState.LIMITED_EVIDENCE
    assert BacktestQualityWarning.LOW_SAMPLE_SIZE in assessment.warnings


def test_large_sample_is_reliable() -> None:
    assessment = BacktestEvaluationQualityService().assess(
        evaluation_count=100,
        minimum_evaluations=30,
        limited_evidence_threshold=60,
    )

    assert assessment.state == BacktestQualityState.RELIABLE
    assert assessment.warnings == ()


def test_low_coverage_downgrades_reliable_assessment() -> None:
    assessment = BacktestEvaluationQualityService().assess(
        evaluation_count=60,
        expected_count=120,
        minimum_evaluations=30,
        limited_evidence_threshold=60,
        minimum_coverage_ratio=0.75,
    )

    assert assessment.coverage_ratio == 0.5
    assert assessment.state == BacktestQualityState.LIMITED_EVIDENCE
    assert BacktestQualityWarning.LOW_COVERAGE in assessment.warnings


def test_coverage_is_capped_at_one() -> None:
    assessment = BacktestEvaluationQualityService().assess(
        evaluation_count=150,
        expected_count=100,
        minimum_evaluations=30,
    )

    assert assessment.coverage_ratio == 1.0


@pytest.mark.parametrize(
    ("evaluation_count", "expected_state"),
    [
        (0, BacktestQualityState.INSUFFICIENT_EVIDENCE),
        (29, BacktestQualityState.INSUFFICIENT_EVIDENCE),
        (30, BacktestQualityState.LIMITED_EVIDENCE),
        (59, BacktestQualityState.LIMITED_EVIDENCE),
        (60, BacktestQualityState.RELIABLE),
    ],
)
def test_quality_boundaries_are_deterministic(
    evaluation_count: int,
    expected_state: BacktestQualityState,
) -> None:
    assessment = BacktestEvaluationQualityService().assess(
        evaluation_count=evaluation_count,
        minimum_evaluations=30,
        limited_evidence_threshold=60,
    )

    assert assessment.state == expected_state


def test_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        BacktestEvaluationQualityService().assess(
            evaluation_count=-1,
        )

    with pytest.raises(ValueError, match="cannot be negative"):
        BacktestEvaluationQualityService().assess(
            evaluation_count=10,
            expected_count=-1,
        )


def test_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        BacktestEvaluationQualityService().assess(
            evaluation_count=10,
            minimum_evaluations=0,
        )

    with pytest.raises(
        ValueError,
        match="greater than or equal",
    ):
        BacktestEvaluationQualityService().assess(
            evaluation_count=10,
            minimum_evaluations=30,
            limited_evidence_threshold=20,
        )

    with pytest.raises(
        ValueError,
        match="between 0 and 1",
    ):
        BacktestEvaluationQualityService().assess(
            evaluation_count=10,
            minimum_coverage_ratio=1.5,
        )

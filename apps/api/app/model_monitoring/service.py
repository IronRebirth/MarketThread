import math
from statistics import mean, pstdev
from uuid import UUID, uuid4

from .models import (
    CalibrationMetrics,
    DriftMetric,
    MarketRegimeMetrics,
    ModelMonitoringReport,
    ModelMonitoringRequest,
    PerformanceMetrics,
)


class ModelMonitoringService:
    """Compute deterministic monitoring metrics from persisted model outputs."""

    def build_report(
        self,
        request: ModelMonitoringRequest,
        *,
        snapshot_id: UUID | None = None,
    ) -> ModelMonitoringReport:
        probabilities = tuple(item.predicted_probability for item in request.predictions)
        labels = tuple(int(item.actual_label) for item in request.predictions)

        performance = self._performance(probabilities, labels)
        calibration = self._calibration(probabilities, labels)
        prediction_drift = self._prediction_drift(probabilities)
        feature_drift = tuple(
            self._feature_drift(name, request.reference_features[name], request.current_features[name])
            for name in sorted(set(request.reference_features) & set(request.current_features))
        )
        market_regime = self._market_regime(request.market_returns)

        notes = []
        if not request.reference_features or not request.current_features:
            notes.append("Feature drift was not assessed because a reference and current feature window were not both supplied.")
        if not request.market_returns:
            notes.append("Market regime was classified as unavailable because no market returns were supplied.")

        return ModelMonitoringReport(
            snapshot_id=snapshot_id or uuid4(),
            model_name=request.model_name,
            model_version=request.model_version,
            window_start=request.window_start,
            window_end=request.window_end,
            observed_at=request.observed_at,
            performance=performance,
            calibration=calibration,
            prediction_drift=prediction_drift,
            feature_drift=feature_drift,
            market_regime=market_regime,
            notes=tuple(notes),
        )

    def _performance(
        self,
        probabilities: tuple[float, ...],
        labels: tuple[int, ...],
    ) -> PerformanceMetrics:
        predicted = tuple(int(probability >= 0.5) for probability in probabilities)
        return PerformanceMetrics(
            sample_count=len(labels),
            accuracy=sum(prediction == label for prediction, label in zip(predicted, labels, strict=True)) / len(labels),
            positive_rate=mean(labels),
            average_confidence=mean(max(probability, 1 - probability) for probability in probabilities),
        )

    def _calibration(
        self,
        probabilities: tuple[float, ...],
        labels: tuple[int, ...],
    ) -> CalibrationMetrics:
        brier = mean((probability - label) ** 2 for probability, label in zip(probabilities, labels, strict=True))
        epsilon = 1e-15
        log_loss = -mean(
            label * math.log(max(probability, epsilon))
            + (1 - label) * math.log(max(1 - probability, epsilon))
            for probability, label in zip(probabilities, labels, strict=True)
        )
        bins: list[list[tuple[float, int]]] = [[] for _ in range(10)]
        for probability, label in zip(probabilities, labels, strict=True):
            bins[min(int(probability * 10), 9)].append((probability, label))
        ece = sum(
            len(items) / len(labels) * abs(mean(probability for probability, _ in items) - mean(label for _, label in items))
            for items in bins
            if items
        )
        return CalibrationMetrics(
            expected_calibration_error=ece,
            brier_score=brier,
            log_loss=log_loss,
        )

    def _prediction_drift(self, probabilities: tuple[float, ...]) -> DriftMetric:
        psi = _psi((0.5, 0.5), _histogram(probabilities))
        return DriftMetric(
            name="prediction_probability",
            psi=psi,
            drifted=psi >= 0.2,
            notes=("PSI uses ten probability bins and compares the current window with a uniform reference distribution.",),
        )

    def _feature_drift(
        self,
        name: str,
        reference: tuple[float, ...],
        current: tuple[float, ...],
    ) -> DriftMetric:
        if not reference or not current:
            return DriftMetric(
                name=name,
                psi=None,
                drifted=False,
                notes=("Insufficient samples for PSI.",),
            )
        reference_hist = _histogram(reference)
        current_hist = _histogram(current, minimum=min(reference), maximum=max(reference))
        psi = _psi(reference_hist, current_hist)
        return DriftMetric(
            name=name,
            psi=psi,
            drifted=psi >= 0.2,
            notes=("PSI threshold: >= 0.20 indicates material distribution drift.",),
        )

    def _market_regime(self, returns: tuple[float, ...]) -> MarketRegimeMetrics:
        if not returns:
            return MarketRegimeMetrics(regime="unavailable", sample_count=0)
        average_return = mean(returns)
        volatility = pstdev(returns) if len(returns) > 1 else 0.0
        if volatility >= 0.02:
            regime = "high_volatility"
        elif average_return >= 0.001:
            regime = "positive_trend"
        elif average_return <= -0.001:
            regime = "negative_trend"
        else:
            regime = "range_bound"
        return MarketRegimeMetrics(
            regime=regime,
            average_return=average_return,
            volatility=volatility,
            sample_count=len(returns),
        )


def _histogram(
    values: tuple[float, ...],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> tuple[float, ...]:
    if not values:
        return (1.0,)
    low = min(values) if minimum is None else minimum
    high = max(values) if maximum is None else maximum
    if high <= low:
        return (1.0,)
    counts = [0] * 10
    for value in values:
        index = min(max(int((value - low) / (high - low) * 10), 0), 9)
        counts[index] += 1
    total = len(values)
    return tuple(max(count / total, 1e-6) for count in counts)


def _psi(reference: tuple[float, ...], current: tuple[float, ...]) -> float:
    size = min(len(reference), len(current))
    return sum(
        (current[index] - reference[index]) * math.log(current[index] / reference[index])
        for index in range(size)
    )

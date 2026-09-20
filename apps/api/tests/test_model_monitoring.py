from datetime import UTC, datetime, timedelta

from app.model_monitoring.models import ModelMonitoringRequest, MonitoringPrediction
from app.model_monitoring.service import ModelMonitoringService


def _request() -> ModelMonitoringRequest:
    now = datetime.now(UTC)
    return ModelMonitoringRequest(
        model_name="signal-model",
        model_version="2026.09",
        window_start=now - timedelta(days=7),
        window_end=now,
        observed_at=now,
        predictions=(
            MonitoringPrediction(predicted_probability=0.9, actual_label=True),
            MonitoringPrediction(predicted_probability=0.8, actual_label=True),
            MonitoringPrediction(predicted_probability=0.2, actual_label=False),
            MonitoringPrediction(predicted_probability=0.1, actual_label=False),
        ),
        reference_features={"momentum": (0.1, 0.2, 0.3, 0.4)},
        current_features={"momentum": (0.1, 0.2, 0.3, 0.4)},
        market_returns=(0.002, 0.001, 0.003, 0.002),
    )


def test_monitoring_report_computes_performance_and_calibration() -> None:
    report = ModelMonitoringService().build_report(_request())

    assert report.performance.sample_count == 4
    assert report.performance.accuracy == 1.0
    assert report.calibration.brier_score == 0.025
    assert report.calibration.expected_calibration_error > 0.0
    assert report.prediction_drift.name == "prediction_probability"


def test_monitoring_report_classifies_market_regime() -> None:
    report = ModelMonitoringService().build_report(_request())

    assert report.market_regime.regime == "positive_trend"
    assert report.market_regime.sample_count == 4


def test_monitoring_report_records_missing_context_limitations() -> None:
    request = _request().model_copy(update={"market_returns": ()})

    report = ModelMonitoringService().build_report(request)

    assert report.market_regime.regime == "unavailable"
    assert any("Market regime" in note for note in report.notes)

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MonitoringPrediction(BaseModel):
    model_config = ConfigDict(frozen=True)

    predicted_probability: float = Field(ge=0.0, le=1.0)
    actual_label: bool


class ModelMonitoringRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_name: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    window_start: datetime
    window_end: datetime
    observed_at: datetime
    predictions: tuple[MonitoringPrediction, ...] = Field(min_length=1)
    reference_predictions: tuple[float, ...] = ()
    reference_features: dict[str, tuple[float, ...]] = Field(default_factory=dict)
    current_features: dict[str, tuple[float, ...]] = Field(default_factory=dict)
    market_returns: tuple[float, ...] = ()

    @model_validator(mode="after")
    def validate_window(self) -> "ModelMonitoringRequest":
        timestamps = (
            self.window_start,
            self.window_end,
            self.observed_at,
        )

        if any(timestamp.tzinfo is None for timestamp in timestamps):
            raise ValueError("Monitoring timestamps must include a timezone.")

        if self.window_end <= self.window_start:
            raise ValueError("window_end must be later than window_start.")

        if self.observed_at < self.window_end:
            raise ValueError("observed_at must not precede window_end.")

        if any(
            probability < 0.0 or probability > 1.0
            for probability in self.reference_predictions
        ):
            raise ValueError(
                "reference_predictions must contain probabilities between 0 and 1.",
            )

        return self


class CalibrationMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_calibration_error: float | None = None
    brier_score: float | None = None
    log_loss: float | None = None


class PerformanceMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_count: int
    accuracy: float | None = None
    positive_rate: float | None = None
    average_confidence: float | None = None


class DriftMetric(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    psi: float | None = None
    drifted: bool
    notes: tuple[str, ...] = ()


class MarketRegimeMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    regime: str
    average_return: float | None = None
    volatility: float | None = None
    sample_count: int


class ModelMonitoringReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: UUID | None = None
    model_name: str
    model_version: str
    window_start: datetime
    window_end: datetime
    observed_at: datetime
    performance: PerformanceMetrics
    calibration: CalibrationMetrics
    prediction_drift: DriftMetric
    feature_drift: tuple[DriftMetric, ...]
    market_regime: MarketRegimeMetrics
    notes: tuple[str, ...] = ()


class ModelMonitoringReportResponse(ModelMonitoringReport):
    created_at: datetime


class ModelMonitoringReportListResponse(BaseModel):
    reports: tuple[ModelMonitoringReportResponse, ...]
    total: int
    limit: int
    offset: int

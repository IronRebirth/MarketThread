export type BacktestQualityState =
  | "reliable"
  | "limited_evidence"
  | "insufficient_evidence";

export type BacktestQualityWarning =
  | "low_sample_size"
  | "no_evaluations"
  | "low_coverage";

export type BacktestPerformanceSummary = {
  state: string;
  evaluation_count: number;
  directional_accuracy: number | null;
  average_forward_return_pct: number | null;
  average_relative_return_pct: number | null;
  positive_outcome_rate: number | null;
  quality_state: BacktestQualityState | null;
};

export type BacktestQualityResponse = {
  state: BacktestQualityState;
  evaluation_count: number;
  expected_count: number;
  coverage_ratio: number;
  minimum_evaluations: number;
  warnings: BacktestQualityWarning[];
  notes: string[];
};

export type BacktestPerformanceReport = {
  backtest_id: string;
  total_evaluations: number;
  valid_evaluations: number;
  rejected_evaluations: number;
  directional_accuracy: number | null;
  average_forward_return_pct: number | null;
  average_relative_return_pct: number | null;
  positive_outcome_rate: number | null;
  quality_state: BacktestQualityState;
  quality_evaluation_count: number;
  quality_expected_count: number;
  quality_coverage_ratio: number;
  quality_minimum_evaluations: number;
  quality_warnings: BacktestQualityWarning[];
  quality_notes: string[];
  by_horizon: {
    summaries: BacktestPerformanceSummary[];
  };
  by_signal_strength: {
    summaries: BacktestPerformanceSummary[];
  };
  by_recommendation_state: {
    summaries: BacktestPerformanceSummary[];
  };
  notes: string[];
};

export type BacktestExecutionPayload = {
  backtest_id: string;
  evaluations?: unknown[];
  fold_results?: unknown[];
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchBacktestPerformanceReport(
  execution: BacktestExecutionPayload,
): Promise<BacktestPerformanceReport> {
  const response = await fetch(`${API_BASE_URL}/backtests/performance-report`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      execution,
    }),
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();

    throw new Error(
      detail || `Backtest report request failed (${response.status})`,
    );
  }

  return (await response.json()) as BacktestPerformanceReport;
}

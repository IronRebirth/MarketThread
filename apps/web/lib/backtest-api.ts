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
  quality_expected_count: number | null;
  quality_coverage_ratio: number | null;
  quality_warnings: BacktestQualityWarning[];
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

export type BacktestProvenanceEvidence = {
  article_id: string;
  source_name: string;
  source_url: string;
  published_at: string | null;
  discovered_at: string;
  retrieved_at: string;
  relevance_note: string;
};

export type BacktestProvenance = {
  result_id: string;
  stage:
    | "news_intelligence"
    | "event_intelligence"
    | "company_impact"
    | "market_impact"
    | "signal_intelligence"
    | "risk_confidence"
    | "recommendation"
    | "backtesting";
  created_at: string;
  ruleset_version: string;
  evidence: BacktestProvenanceEvidence[];
  input_ids: string[];
  assumptions: string[];
  invalidation_conditions: string[];
};

export type BacktestPeriod = {
  start_at: string;
  end_at: string;
};

export type BacktestRunConfiguration = {
  training_periods: BacktestPeriod[];
  evaluation_periods: BacktestPeriod[];
  benchmark_instrument_id: string | null;
};

export type BacktestRunResponse = {
  backtest_id: string;
  valid: boolean;
  evaluation_count: number;
  valid_evaluation_count: number;
  rejected_evaluation_count: number;
  configuration: BacktestRunConfiguration | null;
  created_at: string;
  completed_at: string;
};

export type BacktestRunHistoryResponse = {
  runs: BacktestRunResponse[];
  total: number;
  limit: number;
  offset: number;
};

export type BacktestRunFilters = {
  valid?: boolean;
  completedAfter?: string;
  completedBefore?: string;
};

export type BacktestEvaluationStatus = string;

export type BacktestEvaluationAudit = {
  evaluation_id: string;
  fold_number: number;
  signal_id: string;
  event_id: string;
  instrument_id: string;
  signal_created_at: string;
  status: BacktestEvaluationStatus;
  temporal_error: string | null;
  signal_direction: string;
  observed_direction: string;
  signal_strength: string;
  recommendation_state: string;
  signal_confidence: number | null;
  horizon: string | null;
  forward_return_pct: number | null;
  benchmark_return_pct: number | null;
  relative_return_pct: number | null;
  direction_correct: boolean | null;
  notes: string[];
};

export type BacktestEvaluationAuditResponse = {
  evaluations: BacktestEvaluationAudit[];
  total: number;
  limit: number;
  offset: number;
};

export type BacktestExecutionPayload = {
  backtest_id: string;
  fold_results?: unknown[];
};

export class BacktestApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "BacktestApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function getJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(input, {
    ...init,
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();

    throw new BacktestApiError(
      response.status,
      detail || `Backtest API request failed (${response.status})`,
    );
  }

  return (await response.json()) as T;
}

export async function fetchBacktestPerformanceReport(
  execution: BacktestExecutionPayload,
): Promise<BacktestPerformanceReport> {
  return getJson<BacktestPerformanceReport>(
    `${API_BASE_URL}/backtests/performance-report`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        execution,
      }),
    },
  );
}

export async function fetchLatestBacktestPerformanceReport(): Promise<BacktestPerformanceReport> {
  return getJson<BacktestPerformanceReport>(
    `${API_BASE_URL}/backtests/runs/latest/performance-report`,
  );
}

export async function fetchBacktestPerformanceReportById(
  backtestId: string,
): Promise<BacktestPerformanceReport> {
  return getJson<BacktestPerformanceReport>(
    `${API_BASE_URL}/backtests/runs/${backtestId}/performance-report`,
  );
}

export async function fetchBacktestProvenance(
  backtestId: string,
): Promise<BacktestProvenance> {
  return getJson<BacktestProvenance>(
    `${API_BASE_URL}/backtests/runs/${backtestId}/provenance`,
  );
}

export async function fetchBacktestRuns(
  limit = 20,
  offset = 0,
  filters: BacktestRunFilters = {},
): Promise<BacktestRunHistoryResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  if (filters.valid !== undefined) {
    params.set("valid", String(filters.valid));
  }

  if (filters.completedAfter) {
    params.set("completed_after", filters.completedAfter);
  }

  if (filters.completedBefore) {
    params.set("completed_before", filters.completedBefore);
  }

  return getJson<BacktestRunHistoryResponse>(
    `${API_BASE_URL}/backtests/runs?${params.toString()}`,
  );
}

export async function fetchBacktestEvaluations(
  backtestId: string,
  limit = 50,
  offset = 0,
): Promise<BacktestEvaluationAuditResponse> {
  return getJson<BacktestEvaluationAuditResponse>(
    `${API_BASE_URL}/backtests/runs/${backtestId}/evaluations?limit=${limit}&offset=${offset}`,
  );
}

export async function persistBacktestRun(
  execution: BacktestExecutionPayload,
  configuration?: BacktestRunConfiguration,
): Promise<BacktestRunResponse> {
  return getJson<BacktestRunResponse>(
    `${API_BASE_URL}/backtests/runs`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        execution,
        ...(configuration ? { configuration } : {}),
      }),
    },
  );
}

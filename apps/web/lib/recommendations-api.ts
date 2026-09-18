export type RecommendationState =
  | "consider"
  | "watch"
  | "hold"
  | "reduce"
  | "insufficient_evidence";

export type Recommendation = {
  recommendation_id: string;
  signal_id: string;
  created_at: string;
  event_id: string;
  company_name: string;
  ticker: string | null;
  state: RecommendationState;
  signal_direction: string;
  confidence_score: number;
  risk_score: number;
  confidence_level: string;
  risk_level: string;
  time_horizon: string;
  supporting_factors: string[];
  contradicting_factors: string[];
  assumptions: string[];
  invalidation_conditions: string[];
  evidence_article_ids: string[];
  rationale: string;
};

export type RecommendationProvenance = {
  recommendation_id: string;
  signal_id: string;
  market_impact_id: string;
  event_id: string;
  created_at: string;
  ruleset_version: string;
  input_ids: string[];
  evidence_article_ids: string[];
  assumptions: string[];
  invalidation_conditions: string[];
};

export type RecommendationFilters = {
  signalId?: string;
  companyName?: string;
  ticker?: string;
  state?: RecommendationState;
  startAt?: string;
  endAt?: string;
  limit?: number;
};

export class RecommendationsApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "RecommendationsApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(response: Response): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return `Recommendations API request failed (${response.status})`;
  }

  try {
    const payload = JSON.parse(detail) as { detail?: unknown };

    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // Fall back to the raw response body when it is not JSON.
  }

  return detail;
}

async function getJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(input, {
    ...init,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new RecommendationsApiError(
      response.status,
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as T;
}

function buildQueryParams(filters: RecommendationFilters) {
  const params = new URLSearchParams();

  if (filters.signalId) {
    params.set("signal_id", filters.signalId);
  }

  if (filters.companyName) {
    params.set("company_name", filters.companyName);
  }

  if (filters.ticker) {
    params.set("ticker", filters.ticker.toUpperCase());
  }

  if (filters.state) {
    params.set("state", filters.state);
  }

  if (filters.startAt) {
    params.set("start_at", filters.startAt);
  }

  if (filters.endAt) {
    params.set("end_at", filters.endAt);
  }

  params.set("limit", String(filters.limit ?? 100));

  return params;
}

export async function fetchRecommendations(
  filters: RecommendationFilters = {},
): Promise<Recommendation[]> {
  const params = buildQueryParams(filters);

  return getJson<Recommendation[]>(
    `${API_BASE_URL}/recommendations?${params.toString()}`,
  );
}

export async function generateRecommendationFromSignal(
  signalId: string,
): Promise<Recommendation> {
  return getJson<Recommendation>(
    `${API_BASE_URL}/recommendations/from-signal/${encodeURIComponent(
      signalId,
    )}`,
    {
      method: "POST",
    },
  );
}

export async function fetchRecommendationProvenance(
  recommendationId: string,
): Promise<RecommendationProvenance> {
  return getJson<RecommendationProvenance>(
    `${API_BASE_URL}/recommendations/${encodeURIComponent(
      recommendationId,
    )}/provenance`,
  );
}

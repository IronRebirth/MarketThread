export type SignalDirection =
  | "positive"
  | "negative"
  | "neutral"
  | "uncertain";

export type SignalStrength =
  | "strong"
  | "moderate"
  | "weak"
  | "insufficient";

export type SignalOpportunity =
  | "opportunity"
  | "watch"
  | "hold"
  | "reduce"
  | "insufficient_evidence";

export type MarketSignal = {
  signal_id: string;
  instrument_id: string;
  market_impact_id: string | null;
  created_at: string;
  event_id: string;
  company_name: string;
  ticker: string | null;
  direction: SignalDirection;
  strength: SignalStrength;
  opportunity: SignalOpportunity;
  confidence: number;
  risk_score: number;
  time_horizon: string;
  supporting_factors: string[];
  contradicting_factors: string[];
  evidence_article_ids: string[];
  invalidation_conditions: string[];
  rationale: string;
};

export class SignalsApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "SignalsApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(response: Response): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return `Signals API request failed (${response.status})`;
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
    throw new SignalsApiError(
      response.status,
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as T;
}

export async function fetchMarketSignals(
  limit = 50,
): Promise<MarketSignal[]> {
  const params = new URLSearchParams({
    limit: String(limit),
  });

  return getJson<MarketSignal[]>(
    `${API_BASE_URL}/signals?${params.toString()}`,
  );
}

export async function generateSignalFromMarketImpact(
  marketImpactId: string,
): Promise<MarketSignal> {
  return getJson<MarketSignal>(
    `${API_BASE_URL}/signals/from-market-impact/${encodeURIComponent(
      marketImpactId,
    )}`,
    {
      method: "POST",
    },
  );
}

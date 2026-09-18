export type ImpactType = "direct" | "indirect";

export type CompanyImpactDirection =
  | "positive"
  | "neutral"
  | "negative"
  | "uncertain";

export type ImpactFactor =
  | "demand"
  | "revenue"
  | "input_costs"
  | "financing"
  | "valuation"
  | "supply_chain"
  | "market_access"
  | "regulatory_burden"
  | "competitive_position"
  | "operating_risk"
  | "investor_sentiment"
  | "other";

export type TimeHorizon =
  | "short_term"
  | "medium_term"
  | "long_term"
  | "uncertain";

export type MarketImpact = {
  impact_id: string;
  company_impact_id: string;
  event_id: string;
  company_name: string;
  impact_type: ImpactType;
  direction: CompanyImpactDirection;
  factor: ImpactFactor;
  time_horizon: TimeHorizon;
  confidence: number;
  evidence_article_ids: string[];
  rationale: string;
};

export type MarketImpactFilters = {
  eventId?: string;
  companyName?: string;
  impactType?: ImpactType;
  direction?: CompanyImpactDirection;
  factor?: ImpactFactor;
  timeHorizon?: TimeHorizon;
  startAt?: string;
  endAt?: string;
  limit?: number;
};

export class MarketImpactsApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "MarketImpactsApiError";
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

    throw new MarketImpactsApiError(
      response.status,
      detail ||
        `Market impact API request failed (${response.status})`,
    );
  }

  return (await response.json()) as T;
}

function buildQueryParams(filters: MarketImpactFilters) {
  const params = new URLSearchParams();

  if (filters.eventId) {
    params.set("event_id", filters.eventId);
  }

  if (filters.companyName) {
    params.set("company_name", filters.companyName);
  }

  if (filters.impactType) {
    params.set("impact_type", filters.impactType);
  }

  if (filters.direction) {
    params.set("direction", filters.direction);
  }

  if (filters.factor) {
    params.set("factor", filters.factor);
  }

  if (filters.timeHorizon) {
    params.set("time_horizon", filters.timeHorizon);
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

export async function fetchMarketImpacts(
  filters: MarketImpactFilters = {},
): Promise<MarketImpact[]> {
  const params = buildQueryParams(filters);

  return getJson<MarketImpact[]>(
    `${API_BASE_URL}/market-impacts?${params.toString()}`,
  );
}

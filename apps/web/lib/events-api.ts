export type EventType =
  | "monetary_policy"
  | "inflation"
  | "trade_policy"
  | "geopolitical"
  | "corporate_action"
  | "earnings"
  | "regulation"
  | "macroeconomic"
  | "other";

export type EventCatalyst =
  | "rate_cut"
  | "rate_hike"
  | "inflation_surprise"
  | "tariff"
  | "sanction"
  | "military_escalation"
  | "merger"
  | "acquisition"
  | "earnings_surprise"
  | "regulatory_change"
  | "other";

export type MarketRelevance = "low" | "medium" | "high";

export type ImpactDirection =
  | "positive"
  | "neutral"
  | "negative"
  | "uncertain";

export type MarketEvent = {
  event_id: string;
  event_type: EventType;
  title: string;
  summary: string;
  catalyst: EventCatalyst;
  market_relevance: MarketRelevance;
  impact_direction: ImpactDirection;
  affected_entities: string[];
  affected_sectors: string[];
  source_article_ids: string[];
  first_seen_at: string;
  last_seen_at: string;
  confidence: number;
};

export type EventFilters = {
  eventType?: EventType;
  catalyst?: EventCatalyst;
  marketRelevance?: MarketRelevance;
  impactDirection?: ImpactDirection;
  startAt?: string;
  endAt?: string;
  limit?: number;
};

export class EventsApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "EventsApiError";
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

    throw new EventsApiError(
      response.status,
      detail || `Events API request failed (${response.status})`,
    );
  }

  return (await response.json()) as T;
}

function buildQueryParams(filters: EventFilters) {
  const params = new URLSearchParams();

  if (filters.eventType) {
    params.set("event_type", filters.eventType);
  }

  if (filters.catalyst) {
    params.set("catalyst", filters.catalyst);
  }

  if (filters.marketRelevance) {
    params.set("market_relevance", filters.marketRelevance);
  }

  if (filters.impactDirection) {
    params.set("impact_direction", filters.impactDirection);
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

export async function fetchMarketEvents(
  filters: EventFilters = {},
): Promise<MarketEvent[]> {
  const params = buildQueryParams(filters);

  return getJson<MarketEvent[]>(
    `${API_BASE_URL}/events?${params.toString()}`,
  );
}

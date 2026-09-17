export type ImpactType = "direct" | "indirect";

export type CompanyImpactDirection =
  | "positive"
  | "neutral"
  | "negative"
  | "uncertain";

export type CompanyImpact = {
  impact_id: string;
  event_id: string;
  company_name: string;
  ticker: string | null;
  impact_type: ImpactType;
  direction: CompanyImpactDirection;
  mechanism: string;
  confidence: number;
  evidence_article_ids: string[];
  rationale: string;
};

export type CompanyImpactFilters = {
  eventId?: string;
  companyName?: string;
  ticker?: string;
  impactType?: ImpactType;
  direction?: CompanyImpactDirection;
  startAt?: string;
  endAt?: string;
  limit?: number;
};

export class CompanyImpactsApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "CompanyImpactsApiError";
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

    throw new CompanyImpactsApiError(
      response.status,
      detail ||
        `Company intelligence API request failed (${response.status})`,
    );
  }

  return (await response.json()) as T;
}

function buildQueryParams(filters: CompanyImpactFilters) {
  const params = new URLSearchParams();

  if (filters.eventId) {
    params.set("event_id", filters.eventId);
  }

  if (filters.companyName) {
    params.set("company_name", filters.companyName);
  }

  if (filters.ticker) {
    params.set("ticker", filters.ticker);
  }

  if (filters.impactType) {
    params.set("impact_type", filters.impactType);
  }

  if (filters.direction) {
    params.set("direction", filters.direction);
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

export async function fetchCompanyImpacts(
  filters: CompanyImpactFilters = {},
): Promise<CompanyImpact[]> {
  const params = buildQueryParams(filters);

  return getJson<CompanyImpact[]>(
    `${API_BASE_URL}/company-impacts?${params.toString()}`,
  );
}

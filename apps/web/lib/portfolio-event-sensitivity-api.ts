import { authenticatedFetch } from "./auth-api";

export type PortfolioEventSensitivityItem = {
  market_impact_id: string;
  company_impact_id: string;
  event_id: string;
  company_name: string;
  ticker: string;
  impact_type: "direct" | "indirect";
  direction: "positive" | "neutral" | "negative" | "uncertain";
  factor:
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
  time_horizon: "short_term" | "medium_term" | "long_term" | "uncertain";
  confidence: number;
  event_type:
    | "monetary_policy"
    | "inflation"
    | "trade_policy"
    | "geopolitical"
    | "corporate_action"
    | "earnings"
    | "regulation"
    | "macroeconomic"
    | "other";
  title: string;
  summary: string;
  catalyst:
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
  market_relevance: "low" | "medium" | "high";
  event_impact_direction: "positive" | "neutral" | "negative" | "uncertain";
  affected_entities: string[];
  affected_sectors: string[];
  first_seen_at: string;
  last_seen_at: string;
  event_confidence: number;
  source_article_ids: string[];
  rationale: string;
};

export type PortfolioEventSensitivity = {
  portfolio: {
    portfolio_id: string;
    name: string;
    position_count: number;
  };
  assessed_at: string;
  position_count: number;
  matched_position_count: number;
  unmatched_position_count: number;
  event_count: number;
  impact_count: number;
  returned_impact_count: number;
  quality: "empty" | "none" | "partial" | "sufficient";
  unmatched_symbols: string[];
  methodology: string;
  notes: string[];
  items: PortfolioEventSensitivityItem[];
};

export class PortfolioEventSensitivityApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "PortfolioEventSensitivityApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(response: Response): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return `Portfolio event-sensitivity request failed (${response.status})`;
  }

  try {
    const payload = JSON.parse(detail) as {
      detail?: unknown;
    };

    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // Fall back to the raw response when it is not JSON.
  }

  return detail;
}

export async function fetchPortfolioEventSensitivity(
  portfolioId: string,
  limit = 25,
): Promise<PortfolioEventSensitivity> {
  const response = await authenticatedFetch(
    `${API_BASE_URL}/portfolios/${encodeURIComponent(
      portfolioId,
    )}/event-sensitivity?limit=${encodeURIComponent(String(limit))}`,
  );

  if (!response.ok) {
    throw new PortfolioEventSensitivityApiError(
      response.status,
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as PortfolioEventSensitivity;
}

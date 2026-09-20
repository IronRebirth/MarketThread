import { fetchCompanyImpacts, type CompanyImpact } from "./company-impacts-api";
import { fetchMarketEvents, type MarketEvent } from "./events-api";
import {
  fetchRecommendations,
  type Recommendation,
} from "./recommendations-api";
import { fetchMarketSignals, type MarketSignal } from "./signals-api";
import { authenticatedFetch } from "./auth-api";

export type StockResearchInstrument = {
  id: string;
  symbol: string;
  name: string;
  exchange: string;
  asset_class: string;
  currency: string;
  is_active: boolean;
};

export type StockResearchQuote = {
  instrument_id: string;
  timestamp: string;
  price: string;
  bid: string | null;
  ask: string | null;
  volume: string | null;
  source: string;
};

export type StockResearchBar = {
  instrument_id: string;
  timestamp: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string | null;
  source: string;
};

export type StockResearchQuoteQuality = {
  status: "fresh" | "stale" | "unavailable";
  observed_at: string | null;
  assessed_at: string;
  age_seconds: number | null;
  maximum_age_seconds: number;
  source: string | null;
};

export type StockResearchFundamentals = {
  instrument_id: string;
  period_end: string;
  revenue_growth: string | null;
  earnings_growth: string | null;
  gross_margin: string | null;
  operating_margin: string | null;
  net_margin: string | null;
  roe: string | null;
  roic: string | null;
  debt_to_equity: string | null;
  debt_to_ebitda: string | null;
  operating_cash_flow: string | null;
  free_cash_flow: string | null;
  pe_ratio: string | null;
  ps_ratio: string | null;
  ev_to_ebitda: string | null;
  dividend_yield: string | null;
  source: string;
};

export type StockResearchHistoricalQuality = {
  status: "sufficient" | "insufficient" | "unavailable";
  start: string;
  end: string;
  expected_interval_seconds: number;
  minimum_coverage: number;
  expected_bars: number;
  observed_bars: number;
  missing_bars: number;
  coverage_ratio: number;
  first_observed_at: string | null;
  last_observed_at: string | null;
  sources: string[];
};

export type StockResearchData = {
  instrument: StockResearchInstrument;
  quote: StockResearchQuote | null;
  fundamentals: StockResearchFundamentals | null;
  quoteQuality: StockResearchQuoteQuality | null;
  bars: StockResearchBar[];
  historicalQuality: StockResearchHistoricalQuality | null;
  events: MarketEvent[];
  impacts: CompanyImpact[];
  signals: MarketSignal[];
  recommendations: Recommendation[];
};

export class StockResearchApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "StockResearchApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(response: Response): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return `Stock research request failed (${response.status})`;
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

async function authenticatedJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const response = await authenticatedFetch(input, init);

  if (!response.ok) {
    throw new StockResearchApiError(
      response.status,
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as T;
}

export async function fetchStockResearch(
  symbol: string,
  lookbackDays = 365,
): Promise<StockResearchData> {
  const normalizedSymbol = symbol.trim().toUpperCase();

  if (!normalizedSymbol) {
    throw new StockResearchApiError(422, "Enter a stock symbol.");
  }

  if (
    !Number.isInteger(lookbackDays) ||
    lookbackDays < 30 ||
    lookbackDays > 3650
  ) {
    throw new StockResearchApiError(
      422,
      "The research lookback must be between 30 and 3650 days.",
    );
  }

  const instrument = await authenticatedJson<StockResearchInstrument>(
    `${API_BASE_URL}/market-data/instruments/${encodeURIComponent(
      normalizedSymbol,
    )}`,
  );

  const end = new Date();
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - lookbackDays);

  const startIso = start.toISOString();
  const endIso = end.toISOString();

  const [
    quoteResult,
    fundamentalsResult,
    quoteQualityResult,
    barsResult,
    historicalQualityResult,
    impactsResult,
    signalsResult,
    recommendationsResult,
  ] = await Promise.allSettled([
    authenticatedJson<StockResearchQuote>(
      `${API_BASE_URL}/market-data/instruments/${encodeURIComponent(
        normalizedSymbol,
      )}/quote`,
    ),
    authenticatedJson<StockResearchFundamentals>(
      `${API_BASE_URL}/market-data/instruments/${encodeURIComponent(
        normalizedSymbol,
      )}/fundamentals`,
    ),
    authenticatedJson<StockResearchQuoteQuality>(
      `${API_BASE_URL}/market-data/instruments/${encodeURIComponent(
        normalizedSymbol,
      )}/quote/quality?maximum_age_seconds=900`,
    ),
    authenticatedJson<StockResearchBar[]>(
      `${API_BASE_URL}/market-data/instruments/${encodeURIComponent(
        normalizedSymbol,
      )}/bars?start=${encodeURIComponent(startIso)}&end=${encodeURIComponent(
        endIso,
      )}`,
    ),
    authenticatedJson<StockResearchHistoricalQuality>(
      `${API_BASE_URL}/market-data/instruments/${encodeURIComponent(
        normalizedSymbol,
      )}/bars/quality?start=${encodeURIComponent(
        startIso,
      )}&end=${encodeURIComponent(
        endIso,
      )}&expected_interval_seconds=86400&minimum_coverage=0.9`,
    ),
    fetchCompanyImpacts({
      ticker: normalizedSymbol,
      limit: 100,
    }),
    fetchMarketSignals(500),
    fetchRecommendations({
      ticker: normalizedSymbol,
      limit: 100,
    }),
  ]);

  const quote =
    quoteResult.status === "fulfilled" ? quoteResult.value : null;
  const fundamentals =
    fundamentalsResult.status === "fulfilled"
      ? fundamentalsResult.value
      : null;
  const quoteQuality =
    quoteQualityResult.status === "fulfilled"
      ? quoteQualityResult.value
      : null;
  const bars =
    barsResult.status === "fulfilled" ? barsResult.value : [];
  const historicalQuality =
    historicalQualityResult.status === "fulfilled"
      ? historicalQualityResult.value
      : null;
  const impacts =
    impactsResult.status === "fulfilled" ? impactsResult.value : [];
  const allSignals =
    signalsResult.status === "fulfilled" ? signalsResult.value : [];
  const recommendations =
    recommendationsResult.status === "fulfilled"
      ? recommendationsResult.value
      : [];

  const eventIds = new Set(impacts.map((impact) => impact.event_id));
  const allEvents =
    eventIds.size === 0
      ? []
      : await fetchMarketEvents({
          limit: 100,
        });

  const events = allEvents.filter((event) => eventIds.has(event.event_id));

  const signals = allSignals.filter(
    (signal) =>
      signal.ticker?.trim().toUpperCase() === normalizedSymbol,
  );

  const requiredFailures = [quoteResult, barsResult].filter(
    (result) => result.status === "rejected",
  );

  if (requiredFailures.length === 2 && !quote && bars.length === 0) {
    const reason = requiredFailures[0].reason;

    throw new StockResearchApiError(
      reason instanceof StockResearchApiError ? reason.status : 503,
      reason instanceof Error
        ? reason.message
        : "Market data is currently unavailable.",
    );
  }

  return {
    instrument,
    quote,
    fundamentals,
    quoteQuality,
    bars: [...bars].sort(
      (first, second) =>
        new Date(first.timestamp).getTime() -
        new Date(second.timestamp).getTime(),
    ),
    historicalQuality,
    events,
    impacts,
    signals,
    recommendations,
  };
}

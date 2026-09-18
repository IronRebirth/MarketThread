import { authenticatedFetch } from "./auth-api";

export type Portfolio = {
  portfolio_id: string;
  name: string;
  created_at: string;
  updated_at: string;
  position_count: number;
};

export type PortfolioPosition = {
  position_id: string;
  portfolio_id: string;
  instrument_id: string;
  quantity: string;
  average_cost: string;
  created_at: string;
  updated_at: string;
  symbol: string;
  name: string;
  exchange: string;
  asset_class: string;
  currency: string;
  is_active: boolean;
};

export type PortfolioDetail = Portfolio & {
  positions: PortfolioPosition[];
};

export type PortfolioQuoteResponse = {
  timestamp: string;
  price: string;
  bid: string | null;
  ask: string | null;
  volume: string | null;
  source: string;
};

export type PortfolioQuoteQualityResponse = {
  status: string;
  observed_at: string | null;
  source: string | null;
};

export type PortfolioPositionValuationResponse = {
  position: PortfolioPosition;
  cost_basis: string;
  quote: PortfolioQuoteResponse | null;
  quote_quality: PortfolioQuoteQualityResponse;
  market_value: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_percent: string | null;
};

export type PortfolioCurrencyValuationResponse = {
  currency: string;
  position_count: number;
  quality: string;
  cost_basis: string;
  market_value: string | null;
  unrealized_pnl: string | null;
};

export type PortfolioValuationResponse = {
  portfolio: Portfolio;
  assessed_at: string;
  maximum_quote_age_seconds: number;
  quality: string;
  positions: PortfolioPositionValuationResponse[];
  currencies: PortfolioCurrencyValuationResponse[];
};

export class PortfolioApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "PortfolioApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(response: Response): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return `Portfolio request failed (${response.status})`;
  }

  try {
    const payload = JSON.parse(detail) as {
      detail?: unknown;
    };

    if (typeof payload.detail === "string") {
      return payload.detail;
    }

    if (
      Array.isArray(payload.detail) &&
      payload.detail.every(
        (item) =>
          typeof item === "object" &&
          item !== null &&
          "msg" in item &&
          typeof item.msg === "string",
      )
    ) {
      return payload.detail.map((item) => item.msg).join(" ");
    }
  } catch {
    // Fall back to the raw response when it is not JSON.
  }

  return detail;
}

async function requestJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const response = await authenticatedFetch(input, init);

  if (!response.ok) {
    throw new PortfolioApiError(
      response.status,
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as T;
}

async function requestNoContent(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<void> {
  const response = await authenticatedFetch(input, init);

  if (!response.ok) {
    throw new PortfolioApiError(
      response.status,
      await readErrorMessage(response),
    );
  }
}

export async function fetchPortfolios(): Promise<Portfolio[]> {
  return requestJson<Portfolio[]>(`${API_BASE_URL}/portfolios`);
}

export async function fetchPortfolio(
  portfolioId: string,
): Promise<PortfolioDetail> {
  return requestJson<PortfolioDetail>(
    `${API_BASE_URL}/portfolios/${encodeURIComponent(portfolioId)}`,
  );
}

export async function fetchPortfolioValuation(
  portfolioId: string,
  maximumAgeSeconds = 900,
): Promise<PortfolioValuationResponse> {
  return requestJson<PortfolioValuationResponse>(
    `${API_BASE_URL}/portfolios/${encodeURIComponent(
      portfolioId,
    )}/valuation?maximum_age_seconds=${encodeURIComponent(
      String(maximumAgeSeconds),
    )}`,
  );
}

export async function createPortfolio(
  name: string,
): Promise<Portfolio> {
  return requestJson<Portfolio>(`${API_BASE_URL}/portfolios`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });
}

export async function upsertPortfolioPosition(
  portfolioId: string,
  instrumentId: string,
  quantity: string,
  averageCost: string,
): Promise<PortfolioPosition> {
  return requestJson<PortfolioPosition>(
    `${API_BASE_URL}/portfolios/${encodeURIComponent(
      portfolioId,
    )}/positions/${encodeURIComponent(instrumentId)}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        quantity,
        average_cost: averageCost,
      }),
    },
  );
}

export async function removePortfolioPosition(
  portfolioId: string,
  positionId: string,
): Promise<void> {
  return requestNoContent(
    `${API_BASE_URL}/portfolios/${encodeURIComponent(
      portfolioId,
    )}/positions/${encodeURIComponent(positionId)}`,
    {
      method: "DELETE",
    },
  );
}

export async function deletePortfolio(
  portfolioId: string,
): Promise<void> {
  return requestNoContent(
    `${API_BASE_URL}/portfolios/${encodeURIComponent(portfolioId)}`,
    {
      method: "DELETE",
    },
  );
}

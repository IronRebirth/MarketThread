import { authenticatedFetch } from "./auth-api";

export type PortfolioCashFlowEventType =
  | "deposit"
  | "withdrawal";

export type PortfolioCashFlowResponse = {
  sequence_id: number;
  cash_flow_id: string;
  portfolio_id: string;
  currency: string;
  amount: string;
  event_type: PortfolioCashFlowEventType;
  effective_at: string;
  recorded_at: string;
};

export type PortfolioCashFlowCreateRequest = {
  event_type: PortfolioCashFlowEventType;
  currency: string;
  amount: string;
  effective_at: string;
};

export type FetchPortfolioCashFlowsOptions = {
  startAt?: string;
  endAt?: string;
  limit?: number;
};

export class PortfolioCashFlowApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "PortfolioCashFlowApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(
  response: Response,
): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return `Portfolio cash flow request failed (${response.status})`;
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
    throw new PortfolioCashFlowApiError(
      response.status,
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as T;
}

function buildCashFlowUrl(
  portfolioId: string,
  options: FetchPortfolioCashFlowsOptions = {},
): string {
  const params = new URLSearchParams();

  if (options.startAt) {
    params.set("start_at", options.startAt);
  }

  if (options.endAt) {
    params.set("end_at", options.endAt);
  }

  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }

  const query = params.toString();

  return `${API_BASE_URL}/portfolios/${encodeURIComponent(
    portfolioId,
  )}/cash-flows${query ? `?${query}` : ""}`;
}

export async function fetchPortfolioCashFlows(
  portfolioId: string,
  options: FetchPortfolioCashFlowsOptions = {},
): Promise<PortfolioCashFlowResponse[]> {
  return requestJson<PortfolioCashFlowResponse[]>(
    buildCashFlowUrl(portfolioId, {
      ...options,
      limit: options.limit ?? 500,
    }),
  );
}

export async function createPortfolioCashFlow(
  portfolioId: string,
  request: PortfolioCashFlowCreateRequest,
): Promise<PortfolioCashFlowResponse> {
  return requestJson<PortfolioCashFlowResponse>(
    `${API_BASE_URL}/portfolios/${encodeURIComponent(
      portfolioId,
    )}/cash-flows`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

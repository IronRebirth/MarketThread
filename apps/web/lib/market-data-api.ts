import { authenticatedFetch } from "./auth-api";

export type Instrument = {
  id: string;
  symbol: string;
  name: string;
  exchange: string;
  asset_class: string;
  currency: string;
  is_active: boolean;
};

export class MarketDataApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "MarketDataApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(response: Response): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return `Market-data request failed (${response.status})`;
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

export async function fetchInstrument(
  symbol: string,
): Promise<Instrument> {
  const normalizedSymbol = symbol.trim().toUpperCase();

  const response = await authenticatedFetch(
    `${API_BASE_URL}/market-data/instruments/${encodeURIComponent(
      normalizedSymbol,
    )}`,
  );

  if (!response.ok) {
    throw new MarketDataApiError(
      response.status,
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as Instrument;
}

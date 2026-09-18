import { authenticatedFetch } from "./auth-api";

export type Watchlist = {
  watchlist_id: string;
  name: string;
  created_at: string;
  updated_at: string;
  item_count: number;
};

export type WatchlistItem = {
  item_id: string;
  watchlist_id: string;
  instrument_id: string;
  added_at: string;
  symbol: string;
  name: string;
  exchange: string;
  asset_class: string;
  currency: string;
  is_active: boolean;
};

export type WatchlistDetail = Watchlist & {
  items: WatchlistItem[];
};

export class WatchlistsApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "WatchlistsApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(response: Response): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return `Watchlists request failed (${response.status})`;
  }

  try {
    const payload = JSON.parse(detail) as { detail?: unknown };

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
    // Fall back to the raw response body when it is not JSON.
  }

  return detail;
}

async function requestJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const response = await authenticatedFetch(input, init);

  if (!response.ok) {
    throw new WatchlistsApiError(
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
    throw new WatchlistsApiError(
      response.status,
      await readErrorMessage(response),
    );
  }
}

export async function fetchWatchlists(): Promise<Watchlist[]> {
  return requestJson<Watchlist[]>(`${API_BASE_URL}/watchlists`);
}

export async function fetchWatchlist(
  watchlistId: string,
): Promise<WatchlistDetail> {
  return requestJson<WatchlistDetail>(
    `${API_BASE_URL}/watchlists/${encodeURIComponent(watchlistId)}`,
  );
}

export async function createWatchlist(
  name: string,
): Promise<Watchlist> {
  return requestJson<Watchlist>(`${API_BASE_URL}/watchlists`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });
}

export async function deleteWatchlist(
  watchlistId: string,
): Promise<void> {
  return requestNoContent(
    `${API_BASE_URL}/watchlists/${encodeURIComponent(watchlistId)}`,
    {
      method: "DELETE",
    },
  );
}

export async function addWatchlistItem(
  watchlistId: string,
  instrumentId: string,
): Promise<WatchlistItem> {
  return requestJson<WatchlistItem>(
    `${API_BASE_URL}/watchlists/${encodeURIComponent(
      watchlistId,
    )}/items`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        instrument_id: instrumentId,
      }),
    },
  );
}

export async function fetchWatchlistItems(
  watchlistId: string,
): Promise<WatchlistItem[]> {
  return requestJson<WatchlistItem[]>(
    `${API_BASE_URL}/watchlists/${encodeURIComponent(
      watchlistId,
    )}/items`,
  );
}

export async function removeWatchlistItem(
  watchlistId: string,
  itemId: string,
): Promise<void> {
  return requestNoContent(
    `${API_BASE_URL}/watchlists/${encodeURIComponent(
      watchlistId,
    )}/items/${encodeURIComponent(itemId)}`,
    {
      method: "DELETE",
    },
  );
}

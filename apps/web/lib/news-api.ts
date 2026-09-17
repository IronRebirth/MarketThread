export type MarketRelevance = "low" | "medium" | "high";

export type Sentiment = "positive" | "neutral" | "negative";

export type ImpactDirection =
  | "positive"
  | "neutral"
  | "negative"
  | "uncertain";

export type NewsIntelligence = {
  article_id: string;
  market_relevance: MarketRelevance;
  sentiment: Sentiment;
  impact_direction: ImpactDirection;
  confidence: number;
  topics: string[];
  entities: string[];
  affected_sectors: string[];
  catalyst: string | null;
  rationale: string;
};

export type NewsArticle = {
  article_id: string;
  source_id: string;
  source_name: string;
  source_domain: string;
  title: string;
  url: string;
  summary: string | null;
  author: string | null;
  published_at: string;
  discovered_at: string;
  language: string;
};

export type NewsFeedItem = {
  article: NewsArticle;
  intelligence: NewsIntelligence;
};

export class NewsApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "NewsApiError";
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

    throw new NewsApiError(
      response.status,
      detail || `News API request failed (${response.status})`,
    );
  }

  return (await response.json()) as T;
}

function buildQueryParams({
  query,
  startAt,
  endAt,
  limit,
}: {
  query?: string;
  startAt?: string;
  endAt?: string;
  limit?: number;
}) {
  const params = new URLSearchParams();

  if (query) {
    params.set("query", query);
  }

  if (startAt) {
    params.set("start_at", startAt);
  }

  if (endAt) {
    params.set("end_at", endAt);
  }

  if (limit !== undefined) {
    params.set("limit", String(limit));
  }

  return params;
}

export async function fetchPersistedNews({
  query,
  startAt,
  endAt,
  limit = 50,
}: {
  query?: string;
  startAt?: string;
  endAt?: string;
  limit?: number;
} = {}): Promise<NewsFeedItem[]> {
  const params = buildQueryParams({
    query,
    startAt,
    endAt,
    limit,
  });

  return getJson<NewsFeedItem[]>(
    `${API_BASE_URL}/news?${params.toString()}`,
  );
}

export async function searchAndPersistNews({
  query,
  startAt,
  endAt,
}: {
  query: string;
  startAt?: string;
  endAt?: string;
}): Promise<NewsFeedItem[]> {
  const params = buildQueryParams({
    startAt,
    endAt,
  });

  params.set("query", query);

  return getJson<NewsFeedItem[]>(
    `${API_BASE_URL}/news/search?${params.toString()}`,
  );
}

export async function ingestLatestNews(
  limit = 50,
): Promise<NewsFeedItem[]> {
  const params = new URLSearchParams({
    limit: String(limit),
  });

  return getJson<NewsFeedItem[]>(
    `${API_BASE_URL}/news/latest?${params.toString()}`,
  );
}

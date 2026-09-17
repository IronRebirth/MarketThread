"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchPersistedNews,
  ingestLatestNews,
  NewsApiError,
  searchAndPersistNews,
  type NewsFeedItem,
} from "../../lib/news-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { NewsCard } from "./news-card";

const NEWS_PAGE_SIZE = 50;

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function localDateToIso(value: string, endOfDay = false) {
  if (!value) {
    return undefined;
  }

  const [year, month, day] = value.split("-").map(Number);

  const date = new Date(
    year,
    month - 1,
    day,
    endOfDay ? 23 : 0,
    endOfDay ? 59 : 0,
    endOfDay ? 59 : 0,
    endOfDay ? 999 : 0,
  );

  return date.toISOString();
}

function MetricValue({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <Card>
      <p className="text-sm text-text-secondary">{label}</p>

      <p className="mt-2 text-2xl font-semibold tracking-tight text-text-primary">
        {value}
      </p>

      <p className="mt-2 text-xs leading-5 text-text-muted">
        {description}
      </p>
    </Card>
  );
}

export function NewsIntelligenceDashboard() {
  const [articles, setArticles] = useState<NewsFeedItem[]>([]);
  const [query, setQuery] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(
    null,
  );

  const loadPersistedNews = useCallback(
    async ({
      queryValue = query,
      startDateValue = startDate,
      endDateValue = endDate,
      showLoading = true,
    }: {
      queryValue?: string;
      startDateValue?: string;
      endDateValue?: string;
      showLoading?: boolean;
    } = {}) => {
      if (showLoading) {
        setIsLoading(true);
      }

      setErrorMessage(null);

      try {
        const nextArticles = await fetchPersistedNews({
          query: queryValue.trim() || undefined,
          startAt: localDateToIso(startDateValue),
          endAt: localDateToIso(endDateValue, true),
          limit: NEWS_PAGE_SIZE,
        });

        setArticles(nextArticles);
      } catch (error) {
        setArticles([]);

        setErrorMessage(
          error instanceof NewsApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "The persisted news feed could not be loaded.",
        );
      } finally {
        if (showLoading) {
          setIsLoading(false);
        }
      }
    },
    [endDate, query, startDate],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadPersistedNews();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadPersistedNews]);

  const metrics = useMemo(() => {
    if (articles.length === 0) {
      return {
        articleCount: 0,
        highRelevanceCount: 0,
        negativeImpactCount: 0,
        averageConfidence: null,
      };
    }

    const highRelevanceCount = articles.filter(
      (item) => item.intelligence.market_relevance === "high",
    ).length;

    const negativeImpactCount = articles.filter(
      (item) => item.intelligence.impact_direction === "negative",
    ).length;

    const averageConfidence =
      articles.reduce(
        (total, item) => total + item.intelligence.confidence,
        0,
      ) / articles.length;

    return {
      articleCount: articles.length,
      highRelevanceCount,
      negativeImpactCount,
      averageConfidence,
    };
  }, [articles]);

  const validateDateRange = () => {
    if (startDate && endDate && startDate > endDate) {
      setActionErrorMessage(
        "The start date must be earlier than or equal to the end date.",
      );
      return false;
    }

    return true;
  };

  const handleApplyFilters = () => {
    setActionErrorMessage(null);

    if (!validateDateRange()) {
      return;
    }

    void loadPersistedNews();
  };

  const handleClearFilters = () => {
    setQuery("");
    setStartDate("");
    setEndDate("");
    setActionErrorMessage(null);

    void loadPersistedNews({
      queryValue: "",
      startDateValue: "",
      endDateValue: "",
    });
  };

  const handleSearchAndIngest = async () => {
    const normalizedQuery = query.trim();

    setActionErrorMessage(null);

    if (!normalizedQuery) {
      setActionErrorMessage("Enter a search term before searching news.");
      return;
    }

    if (!validateDateRange()) {
      return;
    }

    setIsSearching(true);

    try {
      const nextArticles = await searchAndPersistNews({
        query: normalizedQuery,
        startAt: localDateToIso(startDate),
        endAt: localDateToIso(endDate, true),
      });

      setArticles(nextArticles);
      setErrorMessage(null);
    } catch (error) {
      setActionErrorMessage(
        error instanceof NewsApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "The news search could not be completed.",
      );
    } finally {
      setIsSearching(false);
    }
  };

  const handleIngestLatest = async () => {
    setActionErrorMessage(null);
    setIsIngesting(true);

    try {
      const nextArticles = await ingestLatestNews(NEWS_PAGE_SIZE);

      if (query || startDate || endDate) {
        await loadPersistedNews({
          showLoading: false,
        });
      } else {
        setArticles(nextArticles);
      }

      setErrorMessage(null);
    } catch (error) {
      setActionErrorMessage(
        error instanceof NewsApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Latest news could not be ingested.",
      );
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">News Intelligence</Badge>
          <Badge variant="positive">API connected</Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              News intelligence
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Explore persisted market news and the deterministic intelligence
              derived from each article.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => void loadPersistedNews()}
              disabled={isLoading || isSearching || isIngesting}
            >
              {isLoading ? "Loading news" : "Refresh feed"}
            </Button>

            <Button
              onClick={() => void handleIngestLatest()}
              disabled={isLoading || isSearching || isIngesting}
            >
              {isIngesting ? "Ingesting news" : "Ingest latest"}
            </Button>
          </div>
        </div>
      </header>

      {errorMessage && (
        <Card
          title="News feed unavailable"
          description="The persisted news workspace could not retrieve articles from the MarketThread API."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button onClick={() => void loadPersistedNews()}>
                Try again
              </Button>
            </div>
          </div>
        </Card>
      )}

      <Card
        title="News search and filters"
        description="Persisted filtering reads from PostgreSQL. Search and ingest retrieves normalized articles through the configured external news provider."
      >
        <div className="flex flex-col gap-5">
          <div className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr_0.6fr]">
            <Input
              id="news-query"
              label="Search terms"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search persisted headlines and summaries"
            />

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-text-primary">
                From
              </span>

              <input
                id="news-start-date"
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2.5 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-text-primary">
                Through
              </span>

              <input
                id="news-end-date"
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2.5 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
              />
            </label>
          </div>

          {actionErrorMessage && (
            <div
              role="alert"
              className="rounded-md border border-border bg-warning-soft px-3 py-2.5 text-sm leading-6 text-warning"
            >
              {actionErrorMessage}
            </div>
          )}

          <div className="flex flex-wrap gap-2 border-t border-border pt-4">
            <Button
              onClick={handleApplyFilters}
              disabled={isLoading || isSearching || isIngesting}
            >
              Apply filters
            </Button>

            <Button
              variant="secondary"
              onClick={() => void handleSearchAndIngest()}
              disabled={isLoading || isSearching || isIngesting}
            >
              {isSearching ? "Searching provider" : "Search & ingest"}
            </Button>

            <Button
              variant="secondary"
              onClick={handleClearFilters}
              disabled={isLoading || isSearching || isIngesting}
            >
              Clear
            </Button>
          </div>
        </div>
      </Card>

      {!isLoading && !errorMessage && (
        <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <MetricValue
            label="Articles"
            value={String(metrics.articleCount)}
            description="Persisted articles currently returned by the feed."
          />

          <MetricValue
            label="High relevance"
            value={String(metrics.highRelevanceCount)}
            description="Articles classified with high market relevance."
          />

          <MetricValue
            label="Negative impact"
            value={String(metrics.negativeImpactCount)}
            description="Articles with a negative directional impact classification."
          />

          <MetricValue
            label="Average confidence"
            value={
              metrics.averageConfidence === null
                ? "—"
                : formatPercentage(metrics.averageConfidence)
            }
            description="Average confidence of the loaded intelligence records."
          />
        </section>
      )}

      {!isLoading && !errorMessage && articles.length === 0 ? (
        <Card
          title="No persisted news"
          description="The news workspace is connected to PostgreSQL, but there are no matching persisted articles."
        >
          <div className="flex min-h-56 items-center justify-center rounded-md border border-border bg-surface-subtle px-6 text-center">
            <div className="max-w-xl">
              <p className="text-sm font-medium text-text-primary">
                No news articles match the current view.
              </p>

              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Use “Ingest latest” to retrieve recent provider data or
                “Search & ingest” to retrieve articles for a specific topic.
                The resulting normalized articles are persisted before they
                appear in this workspace.
              </p>
            </div>
          </div>
        </Card>
      ) : !isLoading && !errorMessage ? (
        <section className="flex flex-col gap-5">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-text-primary">
              Latest news intelligence
            </h2>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Articles are ordered by publication time in the persistence
              layer, with deterministic intelligence shown alongside each
              source article.
            </p>
          </div>

          <div className="flex flex-col gap-5">
            {articles.map((item) => (
              <NewsCard
                key={item.article.article_id}
                item={item}
              />
            ))}
          </div>
        </section>
      ) : (
        <Card
          title="Loading news intelligence"
          description="Retrieving persisted articles and their deterministic classifications."
        >
          <div className="flex flex-col gap-4">
            {[1, 2, 3].map((item) => (
              <div
                key={item}
                className="h-40 animate-pulse rounded-md bg-surface-muted"
              />
            ))}
          </div>
        </Card>
      )}

      {!isLoading && !errorMessage && (
        <Card
          title="Interpretation"
          description="How MarketThread should treat this news intelligence."
        >
          <div className="grid gap-4 md:grid-cols-3">
            <Interpretation
              title="Market relevance"
              description="Describes how strongly an article relates to market-moving information."
            />

            <Interpretation
              title="Confidence"
              description="Represents support for the deterministic classification derived from the article, not the probability of a future market outcome."
            />

            <Interpretation
              title="Impact direction"
              description="Represents the classified directional market implication and can remain uncertain when the evidence does not support a directional conclusion."
            />
          </div>
        </Card>
      )}
    </div>
  );
}

function Interpretation({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle p-4">
      <p className="text-sm font-semibold text-text-primary">{title}</p>

      <p className="mt-2 text-sm leading-6 text-text-secondary">
        {description}
      </p>
    </div>
  );
}

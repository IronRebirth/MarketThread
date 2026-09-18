"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchMarketSignals,
  type MarketSignal,
} from "../../lib/signals-api";
import {
  fetchRecommendations,
  generateRecommendationFromSignal,
  RecommendationsApiError,
  type Recommendation,
  type RecommendationFilters,
  type RecommendationState,
} from "../../lib/recommendations-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { RecommendationCard } from "./recommendation-card";

const recommendationStates: RecommendationState[] = [
  "consider",
  "watch",
  "hold",
  "reduce",
  "insufficient_evidence",
];

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function getStateVariant(state: RecommendationState) {
  if (state === "consider") {
    return "positive" as const;
  }

  if (state === "reduce") {
    return "warning" as const;
  }

  if (state === "insufficient_evidence") {
    return "neutral" as const;
  }

  return "info" as const;
}

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof RecommendationsApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export function RecommendationIntelligenceDashboard() {
  const [recommendations, setRecommendations] = useState<
    Recommendation[]
  >([]);
  const [signals, setSignals] = useState<MarketSignal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSignalsLoading, setIsSignalsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [signalsErrorMessage, setSignalsErrorMessage] = useState<
    string | null
  >(null);

  const [stateFilter, setStateFilter] = useState<
    RecommendationState | ""
  >("");
  const [tickerFilter, setTickerFilter] = useState("");
  const [companyFilter, setCompanyFilter] = useState("");
  const [appliedFilters, setAppliedFilters] =
    useState<RecommendationFilters>({});

  const [generatingSignalId, setGeneratingSignalId] = useState<string | null>(
    null,
  );
  const [generationErrors, setGenerationErrors] = useState<
    Record<string, string>
  >({});

  const loadRecommendations = useCallback(
    async (filters: RecommendationFilters = {}) => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const nextRecommendations = await fetchRecommendations({
          ...filters,
          limit: 100,
        });

        setRecommendations(nextRecommendations);
      } catch (error) {
        setRecommendations([]);

        setErrorMessage(
          getErrorMessage(
            error,
            "Persisted recommendations could not be loaded.",
          ),
        );
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const loadSignals = useCallback(async () => {
    setIsSignalsLoading(true);
    setSignalsErrorMessage(null);

    try {
      const nextSignals = await fetchMarketSignals(30);

      setSignals(nextSignals);
    } catch (error) {
      setSignals([]);

      setSignalsErrorMessage(
        getErrorMessage(
          error,
          "Persisted signals could not be loaded.",
        ),
      );
    } finally {
      setIsSignalsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void Promise.all([
        loadRecommendations(appliedFilters),
        loadSignals(),
      ]);
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [appliedFilters, loadRecommendations, loadSignals]);

  const recommendationMetrics = useMemo(() => {
    if (recommendations.length === 0) {
      return {
        total: 0,
        consider: 0,
        watch: 0,
        insufficient: 0,
        averageConfidence: null,
        averageRisk: null,
      };
    }

    const consider = recommendations.filter(
      (recommendation) => recommendation.state === "consider",
    ).length;

    const watch = recommendations.filter(
      (recommendation) => recommendation.state === "watch",
    ).length;

    const insufficient = recommendations.filter(
      (recommendation) =>
        recommendation.state === "insufficient_evidence",
    ).length;

    const averageConfidence =
      recommendations.reduce(
        (sum, recommendation) => sum + recommendation.confidence_score,
        0,
      ) / recommendations.length;

    const averageRisk =
      recommendations.reduce(
        (sum, recommendation) => sum + recommendation.risk_score,
        0,
      ) / recommendations.length;

    return {
      total: recommendations.length,
      consider,
      watch,
      insufficient,
      averageConfidence,
      averageRisk,
    };
  }, [recommendations]);

  const stateBreakdown = useMemo(() => {
    const counts = new Map<RecommendationState, number>();

    for (const recommendation of recommendations) {
      counts.set(
        recommendation.state,
        (counts.get(recommendation.state) ?? 0) + 1,
      );
    }

    return recommendationStates
      .filter((state) => counts.has(state))
      .map((state) => [state, counts.get(state) ?? 0] as const);
  }, [recommendations]);

  const generatedSignalIds = useMemo(
    () =>
      new Set(
        recommendations.map((recommendation) => recommendation.signal_id),
      ),
    [recommendations],
  );

  const generationCandidates = useMemo(
    () =>
      signals.filter(
        (signal) =>
          !generatedSignalIds.has(signal.signal_id) &&
          signal.market_impact_id !== null,
      ),
    [generatedSignalIds, signals],
  );

  const handleApplyFilters = () => {
    setAppliedFilters({
      companyName: companyFilter.trim() || undefined,
      ticker: tickerFilter.trim() || undefined,
      state: stateFilter || undefined,
    });
  };

  const handleClearFilters = () => {
    setCompanyFilter("");
    setTickerFilter("");
    setStateFilter("");
    setAppliedFilters({});
  };

  const handleGenerate = async (signal: MarketSignal) => {
    setGeneratingSignalId(signal.signal_id);
    setGenerationErrors((current) => {
      const next = { ...current };
      delete next[signal.signal_id];
      return next;
    });

    try {
      await generateRecommendationFromSignal(signal.signal_id);

      await Promise.all([
        loadRecommendations(appliedFilters),
        loadSignals(),
      ]);
    } catch (error) {
      setGenerationErrors((current) => ({
        ...current,
        [signal.signal_id]: getErrorMessage(
          error,
          "The recommendation could not be generated.",
        ),
      }));
    } finally {
      setGeneratingSignalId(null);
    }
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Recommendation Intelligence</Badge>
          <Badge variant="positive">API connected</Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Recommendation intelligence
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Review persisted research recommendations derived from market
              signals, with separate evidence confidence, interpretation
              risk, assumptions, and invalidation conditions.
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() =>
              void Promise.all([
                loadRecommendations(appliedFilters),
                loadSignals(),
              ])
            }
            disabled={
              isLoading ||
              isSignalsLoading ||
              generatingSignalId !== null
            }
          >
            {isLoading ? "Loading recommendations" : "Refresh workspace"}
          </Button>
        </div>
      </header>

      <Card
        title="Recommendation filters"
        description="Filter persisted recommendation snapshots without changing the underlying intelligence."
      >
        <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr_1fr_auto_auto]">
          <label className="flex flex-col gap-2">
            <span className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              State
            </span>

            <select
              value={stateFilter}
              onChange={(event) =>
                setStateFilter(
                  event.target.value as RecommendationState | "",
                )
              }
              className="min-h-10 rounded-md border border-border-strong bg-surface px-3 text-sm text-text-primary outline-none focus:ring-2 focus:ring-brand"
            >
              <option value="">All states</option>

              {recommendationStates.map((state) => (
                <option key={state} value={state}>
                  {formatLabel(state)}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              Ticker
            </span>

            <input
              value={tickerFilter}
              onChange={(event) => setTickerFilter(event.target.value)}
              placeholder="e.g. NVDA"
              className="min-h-10 rounded-md border border-border-strong bg-surface px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:ring-2 focus:ring-brand"
            />
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              Company
            </span>

            <input
              value={companyFilter}
              onChange={(event) => setCompanyFilter(event.target.value)}
              placeholder="Company name"
              className="min-h-10 rounded-md border border-border-strong bg-surface px-3 text-sm text-text-primary placeholder:text-text-muted outline-none focus:ring-2 focus:ring-brand"
            />
          </label>

          <Button
            className="self-end"
            onClick={handleApplyFilters}
          >
            Apply
          </Button>

          <Button
            className="self-end"
            variant="ghost"
            onClick={handleClearFilters}
            disabled={
              !stateFilter &&
              !tickerFilter &&
              !companyFilter &&
              Object.keys(appliedFilters).length === 0
            }
          >
            Clear
          </Button>
        </div>
      </Card>

      {errorMessage && (
        <Card
          title="Recommendation intelligence unavailable"
          description="The dashboard could not retrieve persisted recommendations from the MarketThread API."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button
                onClick={() => void loadRecommendations(appliedFilters)}
              >
                Try again
              </Button>
            </div>
          </div>
        </Card>
      )}

      {!errorMessage && (
        <>
          <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-5">
            <MetricValue
              label="Recommendations"
              value={String(recommendationMetrics.total)}
              description="Persisted snapshots returned by the API."
            />

            <MetricValue
              label="Consider"
              value={String(recommendationMetrics.consider)}
              description="Research states currently classified as consider."
            />

            <MetricValue
              label="Watch"
              value={String(recommendationMetrics.watch)}
              description="Research states requiring continued monitoring."
            />

            <MetricValue
              label="Avg. confidence"
              value={
                recommendationMetrics.averageConfidence === null
                  ? "—"
                  : formatPercentage(
                      recommendationMetrics.averageConfidence,
                    )
              }
              description="Evidence-support score across loaded recommendations."
            />

            <MetricValue
              label="Avg. risk"
              value={
                recommendationMetrics.averageRisk === null
                  ? "—"
                  : formatPercentage(recommendationMetrics.averageRisk)
              }
              description="Interpretation-risk score across loaded recommendations."
            />
          </section>

          <Card
            title="Recommendation landscape"
            description="Distribution of the currently filtered persisted recommendation states."
          >
            {stateBreakdown.length > 0 ? (
              <div className="flex flex-wrap gap-3">
                {stateBreakdown.map(([state, count]) => (
                  <div
                    key={state}
                    className="flex items-center gap-2 rounded-md border border-border bg-surface-subtle px-3 py-2"
                  >
                    <Badge variant={getStateVariant(state)}>
                      {formatLabel(state)}
                    </Badge>

                    <span className="text-sm font-semibold text-text-primary">
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-text-secondary">
                No recommendation states are available for the current
                filter.
              </p>
            )}
          </Card>

          <Card
            title="Generate from persisted signals"
            description="Create a research recommendation from an existing persisted market signal. Generation is explicit and idempotent."
          >
            {isSignalsLoading ? (
              <div className="flex flex-col gap-3">
                {[1, 2, 3].map((item) => (
                  <div
                    key={item}
                    className="h-28 animate-pulse rounded-md bg-surface-muted"
                  />
                ))}
              </div>
            ) : signalsErrorMessage ? (
              <div className="rounded-md border border-border bg-surface-subtle p-4">
                <p className="text-sm leading-6 text-text-secondary">
                  {signalsErrorMessage}
                </p>

                <div className="mt-4">
                  <Button onClick={() => void loadSignals()}>
                    Try again
                  </Button>
                </div>
              </div>
            ) : generationCandidates.length === 0 ? (
              <div className="rounded-md border border-border bg-surface-subtle px-5 py-8 text-center">
                <p className="text-sm font-medium text-text-primary">
                  No eligible signals are waiting for recommendations.
                </p>

                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  A signal must be linked to a persisted market impact, and
                  signals that already have recommendations are excluded from
                  this generation queue.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {generationCandidates.map((signal) => {
                  const isGenerating =
                    generatingSignalId === signal.signal_id;
                  const generationError =
                    generationErrors[signal.signal_id];

                  return (
                    <div
                      key={signal.signal_id}
                      className="rounded-md border border-border bg-surface-subtle p-4"
                    >
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge
                              variant={
                                signal.direction === "negative"
                                  ? "warning"
                                  : signal.direction === "positive"
                                    ? "positive"
                                    : "info"
                              }
                            >
                              {formatLabel(signal.direction)}
                            </Badge>

                            <Badge variant="info">
                              {formatLabel(signal.strength)}
                            </Badge>

                            <Badge variant="neutral">
                              {formatLabel(signal.time_horizon)}
                            </Badge>
                          </div>

                          <h3 className="mt-3 text-base font-semibold text-text-primary">
                            {signal.company_name}

                            {signal.ticker && (
                              <span className="ml-2 font-mono text-sm font-medium text-text-secondary">
                                {signal.ticker}
                              </span>
                            )}
                          </h3>

                          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
                            <span>
                              Confidence: {formatPercentage(signal.confidence)}
                            </span>

                            <span>
                              Risk: {formatPercentage(signal.risk_score)}
                            </span>

                            <span>
                              Evidence: {signal.evidence_article_ids.length}
                            </span>
                          </div>

                          <p className="mt-3 text-sm leading-6 text-text-secondary">
                            {signal.rationale}
                          </p>

                          {generationError && (
                            <p className="mt-3 rounded-md border border-negative-soft bg-negative-soft px-3 py-2 text-sm leading-6 text-negative">
                              {generationError}
                            </p>
                          )}
                        </div>

                        <Button
                          onClick={() => void handleGenerate(signal)}
                          disabled={generatingSignalId !== null}
                        >
                          {isGenerating
                            ? "Generating recommendation"
                            : "Generate recommendation"}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {isLoading ? (
            <Card
              title="Persisted recommendations"
              description="Retrieving recommendation snapshots."
            >
              <div className="h-72 animate-pulse rounded-md bg-surface-muted" />
            </Card>
          ) : recommendations.length === 0 ? (
            <Card
              title="No persisted recommendations"
              description="The current filters returned no recommendation snapshots."
            >
              <div className="flex min-h-52 items-center justify-center rounded-md border border-border bg-surface-subtle px-6 text-center">
                <div className="max-w-xl">
                  <p className="text-sm font-medium text-text-primary">
                    There are no recommendations to display.
                  </p>

                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    Generate a recommendation from an eligible persisted
                    signal above, or clear the filters to inspect the full
                    recommendation history.
                  </p>
                </div>
              </div>
            </Card>
          ) : (
            <section className="flex flex-col gap-5">
              <div>
                <h2 className="text-xl font-semibold tracking-tight text-text-primary">
                  Persisted recommendations
                </h2>

                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  These are immutable recommendation snapshots stored by the
                  backend and linked to their originating signals.
                </p>
              </div>

              <div className="flex flex-col gap-5">
                {recommendations.map((recommendation) => (
                  <RecommendationCard
                    key={recommendation.recommendation_id}
                    recommendation={recommendation}
                  />
                ))}
              </div>
            </section>
          )}

          <Card
            title="Interpretation"
            description="How MarketThread should treat recommendation intelligence."
          >
            <div className="grid gap-4 md:grid-cols-3">
              <Interpretation
                title="Research state"
                description="Recommendation states summarize the structured evidence chain. They are not guarantees of investment performance."
              />

              <Interpretation
                title="Confidence"
                description="Confidence represents evidence support for the interpretation. It is separate from risk and is not a probability of profit."
              />

              <Interpretation
                title="Invalidation"
                description="Each persisted recommendation retains assumptions and invalidation conditions so the reasoning can be revisited when the underlying evidence changes."
              />
            </div>
          </Card>
        </>
      )}
    </div>
  );
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

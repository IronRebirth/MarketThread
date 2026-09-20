"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "../auth/auth-provider";
import {
  EventsApiError,
  fetchMarketEvents,
  type MarketEvent,
} from "../../lib/events-api";
import {
  fetchPortfolioEventSensitivity,
  PortfolioEventSensitivityApiError,
  type PortfolioEventSensitivity,
} from "../../lib/portfolio-event-sensitivity-api";
import {
  fetchPortfolios,
  PortfolioApiError,
  type Portfolio,
} from "../../lib/portfolio-api";
import {
  fetchMarketSignals,
  SignalsApiError,
  type MarketSignal,
} from "../../lib/signals-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { SignalCard } from "./signal-card";
import { SignalGenerationPanel } from "./signal-generation-panel";

const EVENT_LIMIT = 50;
const SIGNAL_LIMIT = 50;
const PORTFOLIO_LIMIT = 25;
const RISK_THRESHOLD = 0.65;

type SectorSummary = {
  name: string;
  mentions: number;
  positive: number;
  negative: number;
  uncertain: number;
};

type ThemeSummary = {
  label: string;
  count: number;
  eventType: MarketEvent["event_type"];
};

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatTimestamp(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function getDirectionVariant(
  direction:
    | MarketEvent["impact_direction"]
    | MarketSignal["direction"],
) {
  if (direction === "positive") {
    return "positive" as const;
  }

  if (direction === "negative") {
    return "negative" as const;
  }

  if (direction === "uncertain") {
    return "warning" as const;
  }

  return "neutral" as const;
}

function getRelevanceVariant(relevance: MarketEvent["market_relevance"]) {
  if (relevance === "high") {
    return "warning" as const;
  }

  if (relevance === "medium") {
    return "info" as const;
  }

  return "neutral" as const;
}

function getOpportunityVariant(
  opportunity: MarketSignal["opportunity"],
) {
  if (opportunity === "opportunity") {
    return "positive" as const;
  }

  if (opportunity === "reduce") {
    return "negative" as const;
  }

  if (opportunity === "insufficient_evidence") {
    return "neutral" as const;
  }

  return "info" as const;
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
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <p className="mt-2 text-2xl font-semibold tracking-tight text-text-primary">
        {value}
      </p>

      <p className="mt-2 text-xs leading-5 text-text-muted">
        {description}
      </p>
    </Card>
  );
}

export function MarketIntelligenceDashboard() {
  const { user, isLoading: isAuthLoading } = useAuth();
  const [events, setEvents] = useState<MarketEvent[]>([]);
  const [signals, setSignals] = useState<MarketSignal[]>([]);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(
    null,
  );
  const [portfolioSensitivity, setPortfolioSensitivity] =
    useState<PortfolioEventSensitivity | null>(null);

  const selectedPortfolioIdRef = useRef<string | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isPortfolioLoading, setIsPortfolioLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [portfolioErrorMessage, setPortfolioErrorMessage] = useState<
    string | null
  >(null);

  const loadSelectedPortfolioSensitivity = useCallback(
    async (portfolioId: string) => {
      setIsPortfolioLoading(true);
      setPortfolioErrorMessage(null);

      try {
        setPortfolioSensitivity(
          await fetchPortfolioEventSensitivity(portfolioId, PORTFOLIO_LIMIT),
        );
      } catch (error) {
        setPortfolioSensitivity(null);
        setPortfolioErrorMessage(
          error instanceof PortfolioEventSensitivityApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "Portfolio event sensitivity could not be loaded.",
        );
      } finally {
        setIsPortfolioLoading(false);
      }
    },
    [],
  );

  const loadWorkspace = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    const [eventsResult, signalsResult] = await Promise.allSettled([
      fetchMarketEvents({ limit: EVENT_LIMIT }),
      fetchMarketSignals(SIGNAL_LIMIT),
    ]);

    const errors: string[] = [];

    if (eventsResult.status === "fulfilled") {
      setEvents(eventsResult.value);
    } else {
      setEvents([]);
      const reason = eventsResult.reason;

      errors.push(
        reason instanceof EventsApiError
          ? reason.message
          : reason instanceof Error
            ? reason.message
            : "The market event feed could not be loaded.",
      );
    }

    if (signalsResult.status === "fulfilled") {
      setSignals(signalsResult.value);
    } else {
      setSignals([]);
      const reason = signalsResult.reason;

      errors.push(
        reason instanceof SignalsApiError
          ? reason.message
          : reason instanceof Error
            ? reason.message
            : "The market signal feed could not be loaded.",
      );
    }

    if (!user) {
      setPortfolios([]);
      setPortfolioSensitivity(null);
      selectedPortfolioIdRef.current = null;
      setSelectedPortfolioId(null);
      setPortfolioErrorMessage(null);
    } else {
      try {
        const nextPortfolios = await fetchPortfolios();
        setPortfolios(nextPortfolios);

        const currentSelectionIsValid =
          selectedPortfolioIdRef.current !== null &&
          nextPortfolios.some(
            (portfolio) =>
              portfolio.portfolio_id === selectedPortfolioIdRef.current,
          );

        const nextPortfolioId = currentSelectionIsValid
          ? selectedPortfolioIdRef.current
          : nextPortfolios[0]?.portfolio_id ?? null;

        selectedPortfolioIdRef.current = nextPortfolioId;
        setSelectedPortfolioId(nextPortfolioId);
        setPortfolioErrorMessage(null);

        if (nextPortfolioId) {
          setIsPortfolioLoading(true);

          try {
            setPortfolioSensitivity(
              await fetchPortfolioEventSensitivity(
                nextPortfolioId,
                PORTFOLIO_LIMIT,
              ),
            );
            setPortfolioErrorMessage(null);
          } catch (error) {
            setPortfolioSensitivity(null);
            setPortfolioErrorMessage(
              error instanceof PortfolioEventSensitivityApiError
                ? error.message
                : error instanceof Error
                  ? error.message
                  : "Portfolio event sensitivity could not be loaded.",
            );
          } finally {
            setIsPortfolioLoading(false);
          }
        } else {
          setPortfolioSensitivity(null);
          setPortfolioErrorMessage(null);
          setIsPortfolioLoading(false);
        }
      } catch (error) {
        setPortfolios([]);
        setPortfolioSensitivity(null);
        selectedPortfolioIdRef.current = null;
        setSelectedPortfolioId(null);
        setPortfolioErrorMessage(
          error instanceof PortfolioApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "Portfolio intelligence could not be loaded.",
        );
      }
    }

    setErrorMessage(errors.length > 0 ? errors.join(" ") : null);
    setIsLoading(false);
  }, [user]);

  useEffect(() => {
    if (isAuthLoading) {
      return;
    }

    const timer = window.setTimeout(() => {
      void loadWorkspace();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [isAuthLoading, loadWorkspace]);

  const metrics = useMemo(() => {
    const highRelevanceEvents = events.filter(
      (event) => event.market_relevance === "high",
    ).length;

    const affectedSectorNames = new Set(
      events.flatMap((event) => event.affected_sectors),
    );

    const riskSignalCount = signals.filter(
      (signal) =>
        signal.risk_score >= RISK_THRESHOLD ||
        signal.opportunity === "reduce",
    ).length;

    const averageConfidence =
      signals.length === 0
        ? null
        : signals.reduce((sum, signal) => sum + signal.confidence, 0) /
          signals.length;

    const averageRisk =
      signals.length === 0
        ? null
        : signals.reduce((sum, signal) => sum + signal.risk_score, 0) /
          signals.length;

    return {
      highRelevanceEvents,
      affectedSectorCount: affectedSectorNames.size,
      riskSignalCount,
      averageConfidence,
      averageRisk,
    };
  }, [events, signals]);

  const recentEvents = useMemo(
    () =>
      [...events]
        .sort(
          (first, second) =>
            new Date(second.first_seen_at).getTime() -
            new Date(first.first_seen_at).getTime(),
        )
        .slice(0, 6),
    [events],
  );

  const opportunities = useMemo(
    () =>
      signals
        .filter((signal) => signal.opportunity === "opportunity")
        .sort(
          (first, second) =>
            second.confidence - first.confidence ||
            second.created_at.localeCompare(first.created_at),
        )
        .slice(0, 6),
    [signals],
  );

  const risks = useMemo(
    () =>
      signals
        .filter(
          (signal) =>
            signal.risk_score >= RISK_THRESHOLD ||
            signal.opportunity === "reduce" ||
            signal.direction === "negative" ||
            signal.direction === "uncertain",
        )
        .sort(
          (first, second) =>
            second.risk_score - first.risk_score ||
            second.confidence - first.confidence,
        )
        .slice(0, 6),
    [signals],
  );

  const sectorSummaries = useMemo<SectorSummary[]>(() => {
    const summaryBySector = new Map<string, SectorSummary>();

    for (const event of events) {
      for (const sector of event.affected_sectors) {
        const normalizedSector = sector.trim();

        if (!normalizedSector) {
          continue;
        }

        const current = summaryBySector.get(normalizedSector) ?? {
          name: normalizedSector,
          mentions: 0,
          positive: 0,
          negative: 0,
          uncertain: 0,
        };

        current.mentions += 1;

        if (event.impact_direction === "positive") {
          current.positive += 1;
        } else if (event.impact_direction === "negative") {
          current.negative += 1;
        } else if (event.impact_direction === "uncertain") {
          current.uncertain += 1;
        }

        summaryBySector.set(normalizedSector, current);
      }
    }

    return [...summaryBySector.values()]
      .sort(
        (first, second) =>
          second.mentions - first.mentions ||
          first.name.localeCompare(second.name),
      )
      .slice(0, 8);
  }, [events]);

  const themeSummaries = useMemo<ThemeSummary[]>(() => {
    const themes = new Map<string, ThemeSummary>();

    for (const event of events) {
      const themeValue =
        event.catalyst !== "other" ? event.catalyst : event.event_type;
      const label = formatLabel(themeValue);

      const current = themes.get(themeValue) ?? {
        label,
        count: 0,
        eventType: event.event_type,
      };

      current.count += 1;
      themes.set(themeValue, current);
    }

    return [...themes.values()]
      .sort(
        (first, second) =>
          second.count - first.count ||
          first.label.localeCompare(second.label),
      )
      .slice(0, 8);
  }, [events]);

  const opportunityCount = signals.filter(
    (signal) => signal.opportunity === "opportunity",
  ).length;

  const averageConfidenceLabel =
    metrics.averageConfidence === null
      ? "—"
      : formatPercentage(metrics.averageConfidence);

  const averageRiskLabel =
    metrics.averageRisk === null
      ? "—"
      : formatPercentage(metrics.averageRisk);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Market Intelligence</Badge>
          <Badge variant="positive">Database backed</Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Global market intelligence
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              A consolidated view of persisted market events, sector activity,
              research signals, risk context, recurring themes, and the latest
              impact on your portfolios.
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() => void loadWorkspace()}
            disabled={isLoading}
          >
            {isLoading ? "Refreshing" : "Refresh intelligence"}
          </Button>
        </div>
      </header>

      {errorMessage && (
        <Card
          title="Some intelligence feeds are unavailable"
          description="The dashboard keeps available persisted sections visible while failed feeds report their own error."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary" role="alert">
              {errorMessage}
            </p>

            <div>
              <Button onClick={() => void loadWorkspace()}>Try again</Button>
            </div>
          </div>
        </Card>
      )}

      <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-5">
        <MetricValue
          label="Recent events"
          value={String(events.length)}
          description={`Latest ${EVENT_LIMIT} persisted events returned by the API.`}
        />

        <MetricValue
          label="High relevance"
          value={String(metrics.highRelevanceEvents)}
          description="Events currently classified as high market relevance."
        />

        <MetricValue
          label="Affected sectors"
          value={String(metrics.affectedSectorCount)}
          description="Distinct sectors represented across the loaded events."
        />

        <MetricValue
          label="Opportunities"
          value={String(opportunityCount)}
          description="Persisted signals currently classified as opportunities."
        />

        <MetricValue
          label="Risk signals"
          value={String(metrics.riskSignalCount)}
          description={`Signals at or above ${formatPercentage(
            RISK_THRESHOLD,
          )} risk, or explicitly marked Reduce.`}
        />
      </section>

      <SignalGenerationPanel
        onGenerated={() => {
          void loadWorkspace();
        }}
      />

      <section className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <Card
          title="Market pulse"
          description="Summary metrics across the currently loaded persisted signal set."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <MetricValue
              label="Loaded signals"
              value={String(signals.length)}
              description={`Latest ${SIGNAL_LIMIT} persisted signals returned by the API.`}
            />

            <MetricValue
              label="Average confidence"
              value={averageConfidenceLabel}
              description="Evidence-support score across the loaded signals."
            />

            <MetricValue
              label="Average risk"
              value={averageRiskLabel}
              description="Persisted risk score kept separate from confidence."
            />

            <MetricValue
              label="Data posture"
              value={
                events.length > 0 || signals.length > 0 ? "Observed" : "Empty"
              }
              description="The dashboard only summarizes persisted observations; it does not create synthetic market data."
            />
          </div>
        </Card>

        <Card
          title="Intelligence coverage"
          description="Current source coverage available to this dashboard."
        >
          <div className="flex flex-col gap-4">
            <CoverageRow label="Events" value={events.length > 0} />
            <CoverageRow label="Signals" value={signals.length > 0} />
            <CoverageRow
              label="Portfolio context"
              value={portfolioSensitivity !== null}
            />

            <p className="border-t border-border pt-4 text-xs leading-5 text-text-muted">
              Coverage describes persisted data availability, not data
              completeness for the entire global market.
            </p>
          </div>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <Card
          title="Recent market events"
          description="Newest persisted events with their documented relevance and affected sectors."
        >
          {isLoading ? (
            <LoadingStack count={5} />
          ) : recentEvents.length === 0 ? (
            <EmptyState
              title="No persisted market events"
              description="The event feed is connected, but there are currently no stored events to summarize."
              href="/events"
              linkLabel="Open events"
            />
          ) : (
            <div className="flex flex-col divide-y divide-border">
              {recentEvents.map((event) => (
                <article
                  key={event.event_id}
                  className="py-4 first:pt-0 last:pb-0"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={getRelevanceVariant(event.market_relevance)}
                    >
                      {formatLabel(event.market_relevance)} relevance
                    </Badge>

                    <Badge
                      variant={getDirectionVariant(event.impact_direction)}
                    >
                      {formatLabel(event.impact_direction)}
                    </Badge>

                    <span className="text-xs text-text-muted">
                      {formatTimestamp(event.first_seen_at)}
                    </span>
                  </div>

                  <h3 className="mt-3 text-sm font-semibold text-text-primary">
                    {event.title}
                  </h3>

                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    {event.summary}
                  </p>

                  {event.affected_sectors.length > 0 && (
                    <p className="mt-3 text-xs leading-5 text-text-muted">
                      Sectors: {event.affected_sectors.slice(0, 4).join(", ")}
                      {event.affected_sectors.length > 4 ? " and more" : ""}
                    </p>
                  )}
                </article>
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Recurring themes"
          description="Theme tags derived from persisted event catalysts and event types."
        >
          {themeSummaries.length === 0 ? (
            <EmptyState
              title="No themes yet"
              description="Themes appear as persisted events accumulate."
              href="/events"
              linkLabel="Open events"
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              {themeSummaries.map((theme) => (
                <div
                  key={theme.label}
                  className="flex items-center justify-between gap-4 rounded-md border border-border bg-surface-subtle px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text-primary">
                      {theme.label}
                    </p>

                    <p className="mt-1 text-xs text-text-muted">
                      {formatLabel(theme.eventType)} events
                    </p>
                  </div>

                  <Badge variant="info">{theme.count}</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <SignalListCard
          title="Opportunities"
          description="Persisted signals explicitly classified as opportunities."
          emptyTitle="No opportunity signals"
          emptyDescription="No loaded signal currently has the opportunity state."
          signals={opportunities}
        />

        <SignalListCard
          title="Risk attention"
          description={`Signals at or above ${formatPercentage(
            RISK_THRESHOLD,
          )} risk, or signals carrying explicit negative / uncertain context.`}
          emptyTitle="No elevated-risk signals"
          emptyDescription="No loaded signal meets the dashboard's risk-attention conditions."
          signals={risks}
          riskMode
        />
      </section>

      <Card
        title="Sector landscape"
        description="Sector frequency and direction counts across the currently loaded event feed. Counts are descriptive, not forecasts."
      >
        {sectorSummaries.length === 0 ? (
          <EmptyState
            title="No sector coverage"
            description="Persisted events do not currently contain affected-sector metadata."
            href="/events"
            linkLabel="Open events"
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {sectorSummaries.map((sector) => (
              <div
                key={sector.name}
                className="rounded-md border border-border bg-surface-subtle p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold text-text-primary">
                    {sector.name}
                  </p>

                  <Badge variant="info">{sector.mentions}</Badge>
                </div>

                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <Badge variant="positive">{sector.positive} positive</Badge>
                  <Badge variant="negative">{sector.negative} negative</Badge>
                  <Badge variant="warning">
                    {sector.uncertain} uncertain
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card
        title="Portfolio impact"
        description="Read-only event sensitivity for the selected persisted portfolio, using exact normalized ticker matching."
      >
        {!user ? (
          <EmptyState
            title="Sign in for portfolio context"
            description="Portfolio impact is user-scoped and is shown after authentication."
            href="/login"
            linkLabel="Open sign in"
          />
        ) : portfolios.length === 0 ? (
          <EmptyState
            title="No portfolios yet"
            description="Create a portfolio to connect current holdings with persisted market events."
            href="/portfolio"
            linkLabel="Open portfolio intelligence"
          />
        ) : (
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <label className="flex min-w-0 flex-col gap-2 md:max-w-sm">
                <span className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                  Portfolio
                </span>

                <select
                  value={selectedPortfolioId ?? ""}
                  onChange={(event) => {
                    const nextId = event.target.value || null;
                    selectedPortfolioIdRef.current = nextId;
                    setSelectedPortfolioId(nextId);

                    if (nextId) {
                      void loadSelectedPortfolioSensitivity(nextId);
                    } else {
                      setPortfolioSensitivity(null);
                    }
                  }}
                  className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-text-primary outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
                  disabled={isPortfolioLoading}
                >
                  {portfolios.map((portfolio) => (
                    <option
                      key={portfolio.portfolio_id}
                      value={portfolio.portfolio_id}
                    >
                      {portfolio.name}
                    </option>
                  ))}
                </select>
              </label>

              <Link
                href="/portfolio"
                className="text-sm font-medium text-brand hover:underline"
              >
                Open portfolio intelligence
              </Link>
            </div>

            {isPortfolioLoading ? (
              <LoadingStack count={3} />
            ) : portfolioErrorMessage ? (
              <div className="rounded-md border border-border bg-surface-subtle p-4">
                <p
                  className="text-sm leading-6 text-text-secondary"
                  role="alert"
                >
                  {portfolioErrorMessage}
                </p>

                {selectedPortfolioId && (
                  <div className="mt-4">
                    <Button
                      variant="secondary"
                      onClick={() =>
                        void loadSelectedPortfolioSensitivity(
                          selectedPortfolioId,
                        )
                      }
                    >
                      Try again
                    </Button>
                  </div>
                )}
              </div>
            ) : portfolioSensitivity ? (
              <PortfolioImpactSummary analysis={portfolioSensitivity} />
            ) : (
              <EmptyState
                title="No portfolio impact snapshot"
                description="Select a portfolio to load its persisted event-sensitivity analysis."
                href="/portfolio"
                linkLabel="Open portfolio intelligence"
              />
            )}
          </div>
        )}
      </Card>

      {signals.length > 0 && (
        <Card
          title="Latest persisted signals"
          description="The existing signal workspace remains available below the market overview."
        >
          <div className="flex flex-col gap-5">
            {signals.slice(0, 6).map((signal) => (
              <SignalCard key={signal.signal_id} signal={signal} />
            ))}
          </div>
        </Card>
      )}

      <Card
        title="Interpretation"
        description="How MarketThread should treat this intelligence."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <Interpretation
            title="Evidence before prediction"
            description="The dashboard summarizes persisted observations and model outputs. It does not invent missing market data or turn a signal into a guaranteed outcome."
          />

          <Interpretation
            title="Confidence is evidence strength"
            description="Confidence represents support for the structured signal or impact assessment. It is not a probability that an investment will be profitable."
          />

          <Interpretation
            title="Coverage has limits"
            description="Sector, theme, risk, and portfolio summaries are derived only from the persisted records returned by their APIs. Missing evidence remains missing."
          />
        </div>
      </Card>
    </div>
  );
}

function CoverageRow({
  label,
  value,
}: {
  label: string;
  value: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-border bg-surface-subtle px-4 py-3">
      <span className="text-sm text-text-secondary">{label}</span>

      <Badge variant={value ? "positive" : "neutral"}>
        {value ? "Available" : "Unavailable"}
      </Badge>
    </div>
  );
}

function SignalListCard({
  title,
  description,
  emptyTitle,
  emptyDescription,
  signals,
  riskMode = false,
}: {
  title: string;
  description: string;
  emptyTitle: string;
  emptyDescription: string;
  signals: MarketSignal[];
  riskMode?: boolean;
}) {
  return (
    <Card title={title} description={description}>
      {signals.length === 0 ? (
        <EmptyState
          title={emptyTitle}
          description={emptyDescription}
          href="/recommendations"
          linkLabel="Open recommendations"
        />
      ) : (
        <div className="flex flex-col gap-3">
          {signals.map((signal) => (
            <div
              key={signal.signal_id}
              className="rounded-md border border-border bg-surface-subtle p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-sm font-semibold text-text-primary">
                    {signal.ticker ?? signal.company_name}
                  </p>

                  <p className="mt-1 text-sm text-text-secondary">
                    {signal.company_name}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge variant={getOpportunityVariant(signal.opportunity)}>
                    {formatLabel(signal.opportunity)}
                  </Badge>

                  <Badge variant={getDirectionVariant(signal.direction)}>
                    {formatLabel(signal.direction)}
                  </Badge>
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <MetricValue
                  label={riskMode ? "Risk" : "Confidence"}
                  value={formatPercentage(
                    riskMode ? signal.risk_score : signal.confidence,
                  )}
                  description={
                    riskMode
                      ? "Persisted risk score for the signal."
                      : "Evidence-support score for the signal."
                  }
                />

                <MetricValue
                  label="Time horizon"
                  value={formatLabel(signal.time_horizon)}
                  description="Persisted assessment horizon."
                />
              </div>

              <p className="mt-4 text-sm leading-6 text-text-secondary">
                {signal.rationale}
              </p>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function PortfolioImpactSummary({
  analysis,
}: {
  analysis: PortfolioEventSensitivity;
}) {
  const affectedTickers = new Set(
    analysis.items.map((item) => item.ticker.trim().toUpperCase()),
  ).size;

  const recentItems = analysis.items.slice(0, 5);

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricValue
          label="Positions"
          value={String(analysis.position_count)}
          description="Current positions in the selected portfolio."
        />

        <MetricValue
          label="Affected holdings"
          value={String(affectedTickers)}
          description="Distinct holdings matched to persisted market impacts."
        />

        <MetricValue
          label="Events"
          value={String(analysis.event_count)}
          description="Persisted events connected to current portfolio tickers."
        />

        <MetricValue
          label="Coverage"
          value={formatLabel(analysis.quality)}
          description="Quality of the current persisted event-sensitivity match."
        />
      </div>

      {recentItems.length === 0 ? (
        <EmptyState
          title="No matching portfolio events"
          description={
            analysis.notes[analysis.notes.length - 1] ??
            "No persisted market-impact records matched the selected portfolio."
          }
          href="/market-impacts"
          linkLabel="Open market impact"
        />
      ) : (
        <div className="flex flex-col divide-y divide-border rounded-md border border-border">
          {recentItems.map((item) => (
            <article key={item.market_impact_id} className="p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={getDirectionVariant(item.direction)}>
                  {formatLabel(item.direction)}
                </Badge>

                <Badge variant={getRelevanceVariant(item.market_relevance)}>
                  {formatLabel(item.market_relevance)} relevance
                </Badge>

                <span className="text-xs text-text-muted">{item.ticker}</span>
              </div>

              <h3 className="mt-3 text-sm font-semibold text-text-primary">
                {item.title}
              </h3>

              <p className="mt-2 text-sm leading-6 text-text-secondary">
                {item.rationale}
              </p>

              <p className="mt-3 text-xs leading-5 text-text-muted">
                Factor: {formatLabel(item.factor)} · Horizon:{" "}
                {formatLabel(item.time_horizon)} · Confidence:{" "}
                {formatPercentage(item.confidence)}
              </p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function LoadingStack({ count }: { count: number }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: count }, (_, index) => (
        <div
          key={index}
          className="h-20 animate-pulse rounded-md bg-surface-muted"
        />
      ))}
    </div>
  );
}

function EmptyState({
  title,
  description,
  href,
  linkLabel,
}: {
  title: string;
  description: string;
  href: string;
  linkLabel: string;
}) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
      <p className="text-sm font-medium text-text-primary">{title}</p>

      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-text-secondary">
        {description}
      </p>

      <Link
        href={href}
        className="mt-4 inline-flex text-sm font-medium text-brand hover:underline"
      >
        {linkLabel}
      </Link>
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

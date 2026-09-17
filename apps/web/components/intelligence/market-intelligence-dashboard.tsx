"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchMarketSignals,
  SignalsApiError,
  type MarketSignal,
} from "../../lib/signals-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { SignalCard } from "./signal-card";

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function getOpportunityVariant(
  opportunity: MarketSignal["opportunity"],
) {
  if (opportunity === "opportunity") {
    return "positive" as const;
  }

  if (opportunity === "reduce") {
    return "warning" as const;
  }

  if (opportunity === "insufficient_evidence") {
    return "neutral" as const;
  }

  return "info" as const;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
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

export function MarketIntelligenceDashboard() {
  const [signals, setSignals] = useState<MarketSignal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadSignals = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextSignals = await fetchMarketSignals(50);

      setSignals(nextSignals);
    } catch (error) {
      setSignals([]);

      setErrorMessage(
        error instanceof SignalsApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "The market intelligence feed could not be loaded.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadSignals();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadSignals]);

  const metrics = useMemo(() => {
    if (signals.length === 0) {
      return {
        signalCount: 0,
        opportunityCount: 0,
        averageConfidence: null,
        averageRisk: null,
      };
    }

    const opportunityCount = signals.filter(
      (signal) => signal.opportunity === "opportunity",
    ).length;

    const averageConfidence =
      signals.reduce((sum, signal) => sum + signal.confidence, 0) /
      signals.length;

    const averageRisk =
      signals.reduce((sum, signal) => sum + signal.risk_score, 0) /
      signals.length;

    return {
      signalCount: signals.length,
      opportunityCount,
      averageConfidence,
      averageRisk,
    };
  }, [signals]);

  const opportunityBreakdown = useMemo(() => {
    const counts = new Map<MarketSignal["opportunity"], number>();

    for (const signal of signals) {
      counts.set(
        signal.opportunity,
        (counts.get(signal.opportunity) ?? 0) + 1,
      );
    }

    return Array.from(counts.entries()).sort(
      ([, firstCount], [, secondCount]) => secondCount - firstCount,
    );
  }, [signals]);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Market Intelligence</Badge>
          <Badge variant="positive">API connected</Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Global market intelligence
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Review persisted market signals with their evidence support,
              risk context, time horizon, rationale, and invalidation
              conditions.
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() => void loadSignals()}
            disabled={isLoading}
          >
            {isLoading ? "Loading signals" : "Refresh signals"}
          </Button>
        </div>
      </header>

      {errorMessage && (
        <Card
          title="Market intelligence unavailable"
          description="The dashboard could not retrieve persisted market signals from the MarketThread API."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button onClick={() => void loadSignals()}>Try again</Button>
            </div>
          </div>
        </Card>
      )}

      {isLoading ? (
        <>
          <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="h-32 animate-pulse rounded-lg bg-surface-muted"
              />
            ))}
          </section>

          <Card
            title="Latest signals"
            description="Retrieving persisted market intelligence."
          >
            <div className="h-64 animate-pulse rounded-md bg-surface-muted" />
          </Card>
        </>
      ) : !errorMessage ? (
        <>
          <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <MetricValue
              label="Persisted signals"
              value={String(metrics.signalCount)}
              description="Latest records returned by the signal API."
            />

            <MetricValue
              label="Opportunities"
              value={String(metrics.opportunityCount)}
              description="Signals currently classified as opportunities."
            />

            <MetricValue
              label="Average confidence"
              value={
                metrics.averageConfidence === null
                  ? "—"
                  : formatPercentage(metrics.averageConfidence)
              }
              description="Average evidence-support score across loaded signals."
            />

            <MetricValue
              label="Average risk"
              value={
                metrics.averageRisk === null
                  ? "—"
                  : formatPercentage(metrics.averageRisk)
              }
              description="Average persisted risk score across loaded signals."
            />
          </section>

          {signals.length === 0 ? (
            <Card
              title="No persisted market signals"
              description="The intelligence workspace is connected to the database-backed signal API, but no signals are currently available."
            >
              <div className="flex min-h-52 items-center justify-center rounded-md border border-border bg-surface-subtle px-6 text-center">
                <div className="max-w-xl">
                  <p className="text-sm font-medium text-text-primary">
                    There are no signals to display yet.
                  </p>

                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    MarketThread will display generated and persisted signals
                    here once the intelligence pipeline produces them. This
                    workspace does not substitute mock market data for
                    persisted intelligence.
                  </p>
                </div>
              </div>
            </Card>
          ) : (
            <>
              <Card
                title="Signal landscape"
                description="Distribution of the currently loaded persisted signal opportunities."
              >
                <div className="flex flex-wrap gap-3">
                  {opportunityBreakdown.map(([opportunity, count]) => (
                    <div
                      key={opportunity}
                      className="flex items-center gap-2 rounded-md border border-border bg-surface-subtle px-3 py-2"
                    >
                      <Badge variant={getOpportunityVariant(opportunity)}>
                        {formatLabel(opportunity)}
                      </Badge>

                      <span className="text-sm font-semibold text-text-primary">
                        {count}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>

              <section className="flex flex-col gap-5">
                <div>
                  <h2 className="text-xl font-semibold tracking-tight text-text-primary">
                    Latest signals
                  </h2>

                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    The feed is ordered by signal creation time in the
                    persistence layer.
                  </p>
                </div>

                <div className="flex flex-col gap-5">
                  {signals.map((signal) => (
                    <SignalCard key={signal.signal_id} signal={signal} />
                  ))}
                </div>
              </section>
            </>
          )}

          <Card
            title="Interpretation"
            description="How MarketThread should treat this intelligence."
          >
            <div className="grid gap-4 md:grid-cols-3">
              <Interpretation
                title="Confidence"
                description="Confidence represents the strength of evidence supporting the signal. It is not a probability that an investment will be profitable."
              />

              <Interpretation
                title="Risk"
                description="Risk is stored separately from confidence so evidence strength and uncertainty are not collapsed into one score."
              />

              <Interpretation
                title="Insufficient evidence"
                description="Signals can explicitly remain in an insufficient-evidence state when the available intelligence does not support a stronger conclusion."
              />
            </div>
          </Card>
        </>
      ) : null}
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

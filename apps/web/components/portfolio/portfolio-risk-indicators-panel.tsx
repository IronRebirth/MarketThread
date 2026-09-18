"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchPortfolioRiskIndicators,
  PortfolioApiError,
  type PortfolioRiskIndicatorsResponse,
} from "../../lib/portfolio-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof PortfolioApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
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

function formatAge(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "Unknown";
  }

  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }

  const minutes = seconds / 60;

  if (minutes < 60) {
    return `${Math.round(minutes)} min`;
  }

  const hours = minutes / 60;

  return `${hours.toFixed(hours >= 10 ? 0 : 1)} hr`;
}

function qualityLabel(value: string) {
  switch (value.toLowerCase()) {
    case "current":
      return "Current";
    case "stale":
      return "Stale";
    case "unavailable":
      return "Unavailable";
    case "empty":
      return "No positions";
    default:
      return value;
  }
}

function qualityVariant(
  value: string,
): "positive" | "warning" | "info" | "neutral" {
  switch (value.toLowerCase()) {
    case "current":
      return "positive";
    case "stale":
      return "warning";
    case "empty":
      return "info";
    default:
      return "neutral";
  }
}

function levelLabel(value: string) {
  switch (value.toLowerCase()) {
    case "attention":
      return "Attention";
    case "information":
      return "Information";
    default:
      return value;
  }
}

function levelVariant(
  value: string,
): "warning" | "info" | "neutral" {
  switch (value.toLowerCase()) {
    case "attention":
      return "warning";
    case "information":
      return "info";
    default:
      return "neutral";
  }
}

function kindLabel(value: string) {
  switch (value) {
    case "valuation_data_quality":
      return "Valuation data quality";
    case "single_instrument_currency_exposure":
      return "Single-instrument concentration";
    case "single_asset_class_currency_exposure":
      return "Single-asset-class concentration";
    default:
      return value.replaceAll("_", " ");
  }
}

export function PortfolioRiskIndicatorsPanel({
  portfolioId,
  refreshKey,
}: {
  portfolioId: string;
  refreshKey: string;
}) {
  const [riskIndicators, setRiskIndicators] =
    useState<PortfolioRiskIndicatorsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(
    null,
  );

  const loadRiskIndicators = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextRiskIndicators =
        await fetchPortfolioRiskIndicators(portfolioId);

      setRiskIndicators(nextRiskIndicators);
    } catch (error) {
      setRiskIndicators(null);
      setErrorMessage(
        getErrorMessage(
          error,
          "The portfolio risk indicators could not be loaded.",
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, [portfolioId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadRiskIndicators();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadRiskIndicators, refreshKey]);

  if (isLoading) {
    return (
      <Card
        title="Portfolio risk indicators"
        description="Evaluating observable structural indicators from portfolio exposure and valuation quality."
      >
        <div className="flex flex-col gap-3">
          {[1, 2, 3].map((item) => (
            <div
              key={item}
              className="h-20 animate-pulse rounded-md bg-surface-muted"
            />
          ))}
        </div>
      </Card>
    );
  }

  if (errorMessage) {
    return (
      <Card
        title="Portfolio risk indicators unavailable"
        description="The portfolio holdings remain available, but the structural risk analysis could not be completed."
      >
        <div className="flex flex-col gap-4">
          <p
            className="text-sm leading-6 text-text-secondary"
            role="alert"
          >
            {errorMessage}
          </p>

          <div>
            <Button onClick={() => void loadRiskIndicators()}>
              Refresh risk indicators
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  if (!riskIndicators) {
    return null;
  }

  const attentionCount = riskIndicators.indicators.filter(
    (indicator) => indicator.level === "attention",
  ).length;

  const informationCount = riskIndicators.indicators.filter(
    (indicator) => indicator.level === "information",
  ).length;

  return (
    <Card
      title="Portfolio risk indicators"
      description="Observable structural indicators derived from portfolio exposure and valuation quality. No aggregate portfolio risk score is inferred."
    >
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3 rounded-md border border-border bg-surface-subtle px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={qualityVariant(riskIndicators.quality)}>
                {qualityLabel(riskIndicators.quality)}
              </Badge>

              <span className="text-xs text-text-muted">
                Maximum quote age{" "}
                {formatAge(
                  riskIndicators.maximum_quote_age_seconds,
                )}
              </span>
            </div>

            <p className="mt-2 text-sm text-text-secondary">
              Assessed{" "}
              {formatTimestamp(riskIndicators.assessed_at)}
            </p>
          </div>

          <Button
            variant="ghost"
            onClick={() => void loadRiskIndicators()}
          >
            Refresh indicators
          </Button>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-md border border-border bg-surface-subtle px-4 py-4">
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              Indicators
            </p>

            <p className="mt-2 text-2xl font-semibold tracking-tight text-text-primary">
              {riskIndicators.indicators.length}
            </p>

            <p className="mt-2 text-xs leading-5 text-text-secondary">
              Observable structural observations returned for this
              portfolio.
            </p>
          </div>

          <div className="rounded-md border border-border bg-surface-subtle px-4 py-4">
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              Attention
            </p>

            <p className="mt-2 text-2xl font-semibold tracking-tight text-text-primary">
              {attentionCount}
            </p>

            <p className="mt-2 text-xs leading-5 text-text-secondary">
              Indicators that warrant closer review of the stated
              condition.
            </p>
          </div>

          <div className="rounded-md border border-border bg-surface-subtle px-4 py-4">
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              Information
            </p>

            <p className="mt-2 text-2xl font-semibold tracking-tight text-text-primary">
              {informationCount}
            </p>

            <p className="mt-2 text-xs leading-5 text-text-secondary">
              Structural observations presented for portfolio
              context.
            </p>
          </div>
        </div>

        {riskIndicators.indicators.length === 0 ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
            <p className="text-sm font-medium text-text-primary">
              No structural indicators were triggered.
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              The current portfolio state does not meet any of the
              documented structural indicator conditions.
            </p>
          </div>
        ) : (
          <section>
            <div className="mb-3">
              <p className="text-sm font-semibold text-text-primary">
                Observed indicators
              </p>

              <p className="mt-1 text-sm leading-6 text-text-secondary">
                Each observation describes a specific portfolio
                condition and its supporting rationale.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {riskIndicators.indicators.map((indicator, index) => (
                <article
                  key={`${indicator.kind}-${indicator.currency ?? "all"}-${indicator.asset_class ?? "all"}-${index}`}
                  className="rounded-md border border-border bg-surface-subtle px-5 py-5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge variant={levelVariant(indicator.level)}>
                      {levelLabel(indicator.level)}
                    </Badge>

                    <span className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                      {kindLabel(indicator.kind)}
                    </span>
                  </div>

                  <h3 className="mt-4 text-base font-semibold text-text-primary">
                    {indicator.title}
                  </h3>

                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    {indicator.rationale}
                  </p>

                  <div className="mt-4 flex flex-wrap gap-2 text-xs">
                    {indicator.currency && (
                      <span className="rounded-full border border-border px-2.5 py-1 font-mono text-text-secondary">
                        Currency: {indicator.currency}
                      </span>
                    )}

                    {indicator.asset_class && (
                      <span className="rounded-full border border-border px-2.5 py-1 text-text-secondary">
                        Asset class: {indicator.asset_class}
                      </span>
                    )}

                    <span className="rounded-full border border-border px-2.5 py-1 text-text-secondary">
                      {indicator.position_count} position
                      {indicator.position_count === 1 ? "" : "s"}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        <div className="rounded-md border border-border bg-surface-subtle px-4 py-4">
          <p className="text-sm font-semibold text-text-primary">
            Indicator interpretation
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            These observations identify documented structural
            conditions in the current portfolio. They are not a
            portfolio loss forecast, expected-return estimate, or
            investment recommendation. Data-quality observations are
            surfaced explicitly rather than hidden behind a composite
            score.
          </p>
        </div>
      </div>
    </Card>
  );
}

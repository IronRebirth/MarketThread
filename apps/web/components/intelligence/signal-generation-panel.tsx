"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchMarketImpacts,
  MarketImpactsApiError,
  type MarketImpact,
} from "../../lib/market-impacts-api";
import {
  generateSignalFromMarketImpact,
  SignalsApiError,
} from "../../lib/signals-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function getDirectionVariant(
  direction: MarketImpact["direction"],
) {
  if (direction === "positive") {
    return "positive" as const;
  }

  if (direction === "negative") {
    return "warning" as const;
  }

  if (direction === "uncertain") {
    return "neutral" as const;
  }

  return "info" as const;
}

function getImpactTypeVariant(
  impactType: MarketImpact["impact_type"],
) {
  return impactType === "direct" ? ("info" as const) : ("neutral" as const);
}

function getErrorMessage(error: unknown, fallback: string) {
  if (
    error instanceof SignalsApiError ||
    error instanceof MarketImpactsApiError
  ) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export function SignalGenerationPanel({
  onGenerated,
}: {
  onGenerated?: () => void;
}) {
  const [impacts, setImpacts] = useState<MarketImpact[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [generatingImpactId, setGeneratingImpactId] = useState<string | null>(
    null,
  );
  const [generatedImpactIds, setGeneratedImpactIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [itemErrors, setItemErrors] = useState<Record<string, string>>({});

  const loadImpacts = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextImpacts = await fetchMarketImpacts({
        limit: 12,
      });

      setImpacts(nextImpacts);
    } catch (error) {
      setImpacts([]);

      setErrorMessage(
        getErrorMessage(
          error,
          "Recent market impacts could not be loaded.",
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadImpacts();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadImpacts]);

  const handleGenerate = async (impact: MarketImpact) => {
    if (!impact.ticker || generatingImpactId !== null) {
      return;
    }

    setGeneratingImpactId(impact.impact_id);
    setItemErrors((current) => {
      const next = { ...current };
      delete next[impact.impact_id];
      return next;
    });

    try {
      await generateSignalFromMarketImpact(impact.impact_id);

      setGeneratedImpactIds((current) => {
        const next = new Set(current);
        next.add(impact.impact_id);
        return next;
      });

      onGenerated?.();
    } catch (error) {
      setItemErrors((current) => ({
        ...current,
        [impact.impact_id]: getErrorMessage(
          error,
          "The signal could not be generated.",
        ),
      }));
    } finally {
      setGeneratingImpactId(null);
    }
  };

  return (
    <Card
      title="Generate signal intelligence"
      description="Convert persisted market impacts into database-backed market signals. Signal generation requires a ticker that resolves to an active persisted instrument."
    >
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-3xl text-sm leading-6 text-text-secondary">
            Generation is explicit rather than automatic. Repeating the
            action for the same market impact is safe because signal
            generation is idempotent.
          </p>

          <Button
            variant="secondary"
            onClick={() => void loadImpacts()}
            disabled={isLoading || generatingImpactId !== null}
          >
            {isLoading ? "Loading impacts" : "Refresh impacts"}
          </Button>
        </div>

        {errorMessage ? (
          <div className="rounded-md border border-border bg-surface-subtle p-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div className="mt-4">
              <Button onClick={() => void loadImpacts()}>Try again</Button>
            </div>
          </div>
        ) : isLoading ? (
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((item) => (
              <div
                key={item}
                className="h-32 animate-pulse rounded-md bg-surface-muted"
              />
            ))}
          </div>
        ) : impacts.length === 0 ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-8 text-center">
            <p className="text-sm font-medium text-text-primary">
              No persisted market impacts are available.
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Generate market impacts from the Market Impact workspace before
              creating signals from them.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {impacts.map((impact) => {
              const isGenerating = generatingImpactId === impact.impact_id;
              const hasGeneratedSignal = generatedImpactIds.has(
                impact.impact_id,
              );
              const itemError = itemErrors[impact.impact_id];

              return (
                <div
                  key={impact.impact_id}
                  className="rounded-md border border-border bg-surface-subtle p-4"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={getImpactTypeVariant(impact.impact_type)}>
                          {formatLabel(impact.impact_type)}
                        </Badge>

                        <Badge variant={getDirectionVariant(impact.direction)}>
                          {formatLabel(impact.direction)}
                        </Badge>

                        {hasGeneratedSignal && (
                          <Badge variant="positive">Signal available</Badge>
                        )}
                      </div>

                      <div className="mt-3">
                        <h3 className="text-base font-semibold text-text-primary">
                          {impact.company_name}
                          {impact.ticker && (
                            <span className="ml-2 font-mono text-sm font-medium text-text-secondary">
                              {impact.ticker}
                            </span>
                          )}
                        </h3>

                        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
                          <span>
                            Factor: {formatLabel(impact.factor)}
                          </span>

                          <span>
                            Horizon: {formatLabel(impact.time_horizon)}
                          </span>

                          <span>
                            Confidence: {formatPercentage(impact.confidence)}
                          </span>
                        </div>
                      </div>

                      <p className="mt-3 text-sm leading-6 text-text-secondary">
                        {impact.rationale}
                      </p>

                      {itemError && (
                        <p className="mt-3 rounded-md border border-negative-soft bg-negative-soft px-3 py-2 text-sm leading-6 text-negative">
                          {itemError}
                        </p>
                      )}
                    </div>

                    <div className="flex w-full shrink-0 flex-col gap-2 lg:w-auto lg:items-end">
                      <Button
                        variant={hasGeneratedSignal ? "secondary" : "primary"}
                        onClick={() => void handleGenerate(impact)}
                        disabled={
                          !impact.ticker ||
                          generatingImpactId !== null
                        }
                      >
                        {isGenerating
                          ? "Generating signal"
                          : !impact.ticker
                            ? "Ticker required"
                            : hasGeneratedSignal
                              ? "Refresh signal"
                              : "Generate signal"}
                      </Button>

                      {!impact.ticker && (
                        <p className="max-w-52 text-right text-xs leading-5 text-text-muted">
                          This impact has no ticker, so the API cannot resolve
                          its active instrument.
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Card>
  );
}

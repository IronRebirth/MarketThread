"use client";

import type { PortfolioValuationResponse } from "../../lib/portfolio-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

function formatTimestamp(value: string | null) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatQuantity(value: string) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 8,
  }).format(numericValue);
}

function formatCurrency(value: string | null, currency: string) {
  if (value === null) {
    return "—";
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return `${value} ${currency}`;
  }

  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 8,
    }).format(numericValue);
  } catch {
    return `${value} ${currency}`;
  }
}

function formatPercentage(value: string | null) {
  if (value === null) {
    return "—";
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return `${value}`;
  }

  return `${new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(numericValue * 100)}%`;
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
    case "fresh":
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
    case "fresh":
    case "current":
      return "positive";
    case "stale":
      return "warning";
    case "unavailable":
      return "neutral";
    case "empty":
      return "info";
    default:
      return "neutral";
  }
}

function pnlClassName(value: string | null) {
  if (value === null) {
    return "text-text-secondary";
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue) || numericValue === 0) {
    return "text-text-secondary";
  }

  return numericValue > 0 ? "text-positive" : "text-negative";
}

function getObservedAt(
  observedAt: string | null,
  quoteTimestamp: string | null,
) {
  return observedAt ?? quoteTimestamp;
}

export function PortfolioValuationPanel({
  valuation,
  isLoading,
  errorMessage,
  onRefresh,
}: {
  valuation: PortfolioValuationResponse | null;
  isLoading: boolean;
  errorMessage: string | null;
  onRefresh: () => void;
}) {
  if (isLoading) {
    return (
      <Card
        title="Portfolio valuation"
        description="Assessing persisted positions against the latest available market quotes."
      >
        <div className="flex flex-col gap-3">
          {[1, 2, 3].map((item) => (
            <div
              key={item}
              className="h-16 animate-pulse rounded-md bg-surface-muted"
            />
          ))}
        </div>
      </Card>
    );
  }

  if (errorMessage) {
    return (
      <Card
        title="Portfolio valuation unavailable"
        description="The persisted holdings remain available, but the valuation request could not be completed."
      >
        <div className="flex flex-col gap-4">
          <p className="text-sm leading-6 text-text-secondary" role="alert">
            {errorMessage}
          </p>

          <div>
            <Button onClick={onRefresh}>Refresh valuation</Button>
          </div>
        </div>
      </Card>
    );
  }

  if (!valuation) {
    return null;
  }

  return (
    <Card
      title="Portfolio valuation"
      description="Market value and unrealized performance are calculated server-side from persisted positions and quote freshness."
    >
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3 rounded-md border border-border bg-surface-subtle px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={qualityVariant(valuation.quality)}>
                {qualityLabel(valuation.quality)}
              </Badge>

              <span className="text-xs text-text-muted">
                Maximum quote age{" "}
                {formatAge(valuation.maximum_quote_age_seconds)}
              </span>
            </div>

            <p className="mt-2 text-sm text-text-secondary">
              Assessed {formatTimestamp(valuation.assessed_at)}
            </p>
          </div>

          <Button variant="ghost" onClick={onRefresh}>
            Refresh valuation
          </Button>
        </div>

        {valuation.currencies.length === 0 ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
            <p className="text-sm font-medium text-text-primary">
              No positions to value.
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Add a persisted position to begin calculating market value and
              unrealized performance.
            </p>
          </div>
        ) : (
          <>
            <div>
              <div className="mb-3">
                <p className="text-sm font-semibold text-text-primary">
                  Valuation by currency
                </p>

                <p className="mt-1 text-sm leading-6 text-text-secondary">
                  Currencies remain separate because no FX conversion is
                  applied by the portfolio valuation layer.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {valuation.currencies.map((currencyValuation) => (
                  <div
                    key={currencyValuation.currency}
                    className="rounded-md border border-border bg-surface-subtle px-4 py-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-mono text-sm font-semibold text-text-primary">
                          {currencyValuation.currency}
                        </p>

                        <p className="mt-1 text-xs text-text-muted">
                          {currencyValuation.position_count} position
                          {currencyValuation.position_count === 1 ? "" : "s"}
                        </p>
                      </div>

                      <Badge
                        variant={qualityVariant(
                          currencyValuation.quality,
                        )}
                      >
                        {qualityLabel(currencyValuation.quality)}
                      </Badge>
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-3 md:grid-cols-1 xl:grid-cols-3">
                      <div>
                        <p className="text-xs text-text-muted">Cost basis</p>
                        <p className="mt-1 text-sm font-medium text-text-primary">
                          {formatCurrency(
                            currencyValuation.cost_basis,
                            currencyValuation.currency,
                          )}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs text-text-muted">
                          Market value
                        </p>
                        <p className="mt-1 text-sm font-medium text-text-primary">
                          {formatCurrency(
                            currencyValuation.market_value,
                            currencyValuation.currency,
                          )}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs text-text-muted">
                          Unrealized P&amp;L
                        </p>
                        <p
                          className={[
                            "mt-1 text-sm font-medium",
                            pnlClassName(currencyValuation.unrealized_pnl),
                          ].join(" ")}
                        >
                          {formatCurrency(
                            currencyValuation.unrealized_pnl,
                            currencyValuation.currency,
                          )}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="mb-3">
                <p className="text-sm font-semibold text-text-primary">
                  Position valuation
                </p>

                <p className="mt-1 text-sm leading-6 text-text-secondary">
                  A position only receives current market value when the quote
                  satisfies the configured freshness threshold.
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[1120px] border-separate border-spacing-0">
                  <thead>
                    <tr className="text-left">
                      <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Instrument
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Quantity
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Cost basis
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Current price
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Market value
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Unrealized P&amp;L
                      </th>

                      <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Quote quality
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {valuation.positions.map((positionValuation) => {
                      const position =
                        positionValuation.position;
                      const quote = positionValuation.quote;
                      const quality =
                        positionValuation.quote_quality;

                      const observedAt = getObservedAt(
                        quality.observed_at,
                        quote?.timestamp ?? null,
                      );

                      return (
                        <tr key={position.position_id}>
                          <td className="border-b border-border px-3 py-4">
                            <div>
                              <p className="font-mono text-sm font-semibold text-text-primary">
                                {position.symbol}
                              </p>

                              <p className="mt-1 text-sm text-text-secondary">
                                {position.name}
                              </p>

                              <p className="mt-1 text-xs text-text-muted">
                                {position.exchange}
                              </p>
                            </div>
                          </td>

                          <td className="border-b border-border px-3 py-4 text-right font-mono text-sm text-text-primary">
                            {formatQuantity(position.quantity)}
                          </td>

                          <td className="border-b border-border px-3 py-4 text-right text-sm text-text-primary">
                            {formatCurrency(
                              positionValuation.cost_basis,
                              position.currency,
                            )}
                          </td>

                          <td className="border-b border-border px-3 py-4 text-right text-sm text-text-primary">
                            {quote
                              ? formatCurrency(
                                  quote.price,
                                  position.currency,
                                )
                              : "—"}
                          </td>

                          <td className="border-b border-border px-3 py-4 text-right text-sm font-medium text-text-primary">
                            {formatCurrency(
                              positionValuation.market_value,
                              position.currency,
                            )}
                          </td>

                          <td className="border-b border-border px-3 py-4 text-right">
                            <div
                              className={[
                                "text-sm font-medium",
                                pnlClassName(
                                  positionValuation.unrealized_pnl,
                                ),
                              ].join(" ")}
                            >
                              {formatCurrency(
                                positionValuation.unrealized_pnl,
                                position.currency,
                              )}
                            </div>

                            <p className="mt-1 text-xs text-text-muted">
                              {formatPercentage(
                                positionValuation.unrealized_pnl_percent,
                              )}
                            </p>
                          </td>

                          <td className="border-b border-border px-3 py-4">
                            <div className="flex flex-col items-start gap-2">
                              <Badge
                                variant={qualityVariant(quality.status)}
                              >
                                {qualityLabel(quality.status)}
                              </Badge>

                              {observedAt && (
                                <p className="text-xs leading-5 text-text-muted">
                                  Observed {formatTimestamp(observedAt)}
                                </p>
                              )}

                              {quality.source && (
                                <p className="text-xs leading-5 text-text-muted">
                                  Source: {quality.source}
                                </p>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

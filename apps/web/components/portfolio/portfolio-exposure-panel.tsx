"use client";

import type { PortfolioExposureResponse } from "../../lib/portfolio-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

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
    return "—";
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
    case "current":
    case "fresh":
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
    case "fresh":
      return "positive";
    case "stale":
      return "warning";
    case "empty":
      return "info";
    default:
      return "neutral";
  }
}

export function PortfolioExposurePanel({
  exposure,
  isLoading,
  errorMessage,
  onRefresh,
}: {
  exposure: PortfolioExposureResponse | null;
  isLoading: boolean;
  errorMessage: string | null;
  onRefresh: () => void;
}) {
  if (isLoading) {
    return (
      <Card
        title="Portfolio exposure"
        description="Calculating deterministic exposure and concentration from persisted positions and valuation data."
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
        title="Portfolio exposure unavailable"
        description="The persisted holdings remain available, but the exposure analysis could not be completed."
      >
        <div className="flex flex-col gap-4">
          <p
            className="text-sm leading-6 text-text-secondary"
            role="alert"
          >
            {errorMessage}
          </p>

          <div>
            <Button onClick={onRefresh}>Refresh exposure</Button>
          </div>
        </div>
      </Card>
    );
  }

  if (!exposure) {
    return null;
  }

  return (
    <Card
      title="Portfolio exposure"
      description="Deterministic exposure and concentration metrics derived from the portfolio valuation layer."
    >
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3 rounded-md border border-border bg-surface-subtle px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={qualityVariant(exposure.quality)}>
                {qualityLabel(exposure.quality)}
              </Badge>

              <span className="text-xs text-text-muted">
                Maximum quote age{" "}
                {formatAge(exposure.maximum_quote_age_seconds)}
              </span>
            </div>

            <p className="mt-2 text-sm text-text-secondary">
              Assessed {formatTimestamp(exposure.assessed_at)}
            </p>
          </div>

          <Button variant="ghost" onClick={onRefresh}>
            Refresh exposure
          </Button>
        </div>

        {exposure.currencies.length === 0 ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
            <p className="text-sm font-medium text-text-primary">
              No exposure to display.
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Add a persisted position to establish portfolio exposure.
            </p>
          </div>
        ) : (
          <>
            <section>
              <div className="mb-3">
                <p className="text-sm font-semibold text-text-primary">
                  Currency exposure
                </p>

                <p className="mt-1 text-sm leading-6 text-text-secondary">
                  Currency buckets are kept separate. No FX conversion or
                  cross-currency portfolio weight is inferred.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {exposure.currencies.map((currency) => (
                  <div
                    key={currency.currency}
                    className="rounded-md border border-border bg-surface-subtle px-4 py-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-mono text-sm font-semibold text-text-primary">
                          {currency.currency}
                        </p>

                        <p className="mt-1 text-xs text-text-muted">
                          {currency.position_count} position
                          {currency.position_count === 1 ? "" : "s"}
                        </p>
                      </div>

                      <Badge variant={qualityVariant(currency.quality)}>
                        {qualityLabel(currency.quality)}
                      </Badge>
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div>
                        <p className="text-xs text-text-muted">
                          Cost basis
                        </p>

                        <p className="mt-1 text-sm font-medium text-text-primary">
                          {formatCurrency(
                            currency.cost_basis,
                            currency.currency,
                          )}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs text-text-muted">
                          Market value
                        </p>

                        <p className="mt-1 text-sm font-medium text-text-primary">
                          {formatCurrency(
                            currency.market_value,
                            currency.currency,
                          )}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <div className="mb-3">
                <p className="text-sm font-semibold text-text-primary">
                  Asset-class exposure
                </p>

                <p className="mt-1 text-sm leading-6 text-text-secondary">
                  Asset-class concentration is measured only within the
                  corresponding currency market-value basis.
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] border-separate border-spacing-0">
                  <thead>
                    <tr className="text-left">
                      <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Currency
                      </th>

                      <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Asset class
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Positions
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Cost basis
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Market value
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Currency weight
                      </th>

                      <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Quality
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {exposure.asset_classes.map((assetClass) => (
                      <tr
                        key={`${assetClass.currency}-${assetClass.asset_class}`}
                      >
                        <td className="border-b border-border px-3 py-4 font-mono text-sm text-text-primary">
                          {assetClass.currency}
                        </td>

                        <td className="border-b border-border px-3 py-4 text-sm text-text-primary">
                          {assetClass.asset_class}
                        </td>

                        <td className="border-b border-border px-3 py-4 text-right font-mono text-sm text-text-primary">
                          {assetClass.position_count}
                        </td>

                        <td className="border-b border-border px-3 py-4 text-right text-sm text-text-primary">
                          {formatCurrency(
                            assetClass.cost_basis,
                            assetClass.currency,
                          )}
                        </td>

                        <td className="border-b border-border px-3 py-4 text-right text-sm text-text-primary">
                          {formatCurrency(
                            assetClass.market_value,
                            assetClass.currency,
                          )}
                        </td>

                        <td className="border-b border-border px-3 py-4 text-right text-sm font-medium text-text-primary">
                          {formatPercentage(
                            assetClass.market_value_weight,
                          )}
                        </td>

                        <td className="border-b border-border px-3 py-4">
                          <Badge
                            variant={qualityVariant(assetClass.quality)}
                          >
                            {qualityLabel(assetClass.quality)}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section>
              <div className="mb-3">
                <p className="text-sm font-semibold text-text-primary">
                  Position concentration
                </p>

                <p className="mt-1 text-sm leading-6 text-text-secondary">
                  Position weights are measured against the current
                  market-value total for the same currency.
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[1040px] border-separate border-spacing-0">
                  <thead>
                    <tr className="text-left">
                      <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Instrument
                      </th>

                      <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Currency
                      </th>

                      <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Asset class
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Cost basis
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Market value
                      </th>

                      <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Currency weight
                      </th>

                      <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                        Quality
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {exposure.positions.map((positionExposure) => {
                      const position = positionExposure.position;

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

                          <td className="border-b border-border px-3 py-4 font-mono text-sm text-text-primary">
                            {position.currency}
                          </td>

                          <td className="border-b border-border px-3 py-4 text-sm text-text-primary">
                            {position.asset_class}
                          </td>

                          <td className="border-b border-border px-3 py-4 text-right text-sm text-text-primary">
                            {formatCurrency(
                              positionExposure.cost_basis,
                              position.currency,
                            )}
                          </td>

                          <td className="border-b border-border px-3 py-4 text-right text-sm font-medium text-text-primary">
                            {formatCurrency(
                              positionExposure.market_value,
                              position.currency,
                            )}
                          </td>

                          <td className="border-b border-border px-3 py-4 text-right text-sm font-medium text-text-primary">
                            {formatPercentage(
                              positionExposure.market_value_weight,
                            )}
                          </td>

                          <td className="border-b border-border px-3 py-4">
                            <Badge
                              variant={qualityVariant(
                                positionExposure.quality,
                              )}
                            >
                              {qualityLabel(positionExposure.quality)}
                            </Badge>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            <div className="rounded-md border border-border bg-surface-subtle px-4 py-4">
              <p className="text-sm font-semibold text-text-primary">
                Exposure interpretation
              </p>

              <p className="mt-2 text-sm leading-6 text-text-secondary">
                These metrics describe observable allocation and
                concentration. They are not a portfolio risk score, loss
                forecast, or investment recommendation. Stale or unavailable
                quote data intentionally leaves market-value weights
                unavailable.
              </p>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

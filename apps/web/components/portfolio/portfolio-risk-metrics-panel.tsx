import {
  type PortfolioCurrencyRiskMetricsResponse,
  type PortfolioRiskMetricsResponse,
} from "../../lib/portfolio-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

type PortfolioRiskMetricsPanelProps = {
  riskMetrics: PortfolioRiskMetricsResponse | null;
  isLoading: boolean;
  errorMessage: string | null;
  lookbackDays: number;
  onLookbackDaysChange: (lookbackDays: number) => void;
  onRefresh: () => void;
};

const LOOKBACK_OPTIONS = [
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
  { value: 365, label: "1 year" },
  { value: 730, label: "2 years" },
];

function getQualityVariant(
  quality: PortfolioCurrencyRiskMetricsResponse["quality"],
): "positive" | "warning" | "neutral" | "info" {
  switch (quality) {
    case "sufficient":
      return "positive";
    case "insufficient":
      return "warning";
    case "unavailable":
      return "neutral";
    case "empty":
      return "info";
  }
}

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "—";
  }

  return `${new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
  }).format(value * 100)}%`;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  const date = new Date(`${value}T00:00:00Z`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(date);
}

function formatTimestamp(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function CurrencyRiskMetricsCard({
  metrics,
}: {
  metrics: PortfolioCurrencyRiskMetricsResponse;
}) {
  return (
    <div className="rounded-md border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-lg font-semibold text-text-primary">
            {metrics.currency}
          </p>

          <p className="mt-1 text-sm text-text-secondary">
            {metrics.position_count} position
            {metrics.position_count === 1 ? "" : "s"} ·{" "}
            {metrics.observation_count} complete observation
            {metrics.observation_count === 1 ? "" : "s"}
          </p>
        </div>

        <Badge variant={getQualityVariant(metrics.quality)}>
          {metrics.quality}
        </Badge>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <RiskMetric
          label="Annualized volatility"
          value={formatPercent(metrics.annualized_volatility)}
        />

        <RiskMetric
          label="Maximum drawdown"
          value={formatPercent(metrics.maximum_drawdown)}
        />

        <RiskMetric
          label="Return observations"
          value={metrics.return_count.toLocaleString()}
        />

        <RiskMetric
          label="Positions"
          value={metrics.position_count.toLocaleString()}
        />
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <RiskMetric
          label="First observed"
          value={formatDate(metrics.first_observed_on)}
        />

        <RiskMetric
          label="Last observed"
          value={formatDate(metrics.last_observed_on)}
        />

        <RiskMetric
          label="Drawdown peak"
          value={formatDate(metrics.drawdown_peak_on)}
        />

        <RiskMetric
          label="Drawdown trough"
          value={formatDate(metrics.drawdown_trough_on)}
        />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Data sources
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {metrics.sources.length > 0
              ? metrics.sources.join(", ")
              : "No source recorded"}
          </p>
        </div>

        <div>
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Coverage
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {metrics.observation_count.toLocaleString()} complete
            observations and{" "}
            {metrics.return_count.toLocaleString()} simple return
            observations.
          </p>
        </div>
      </div>

      {metrics.notes.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Method notes
          </p>

          <ul className="mt-2 space-y-1 text-sm leading-6 text-text-secondary">
            {metrics.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function RiskMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <p className="mt-2 text-sm font-semibold text-text-primary">
        {value}
      </p>
    </div>
  );
}

export function PortfolioRiskMetricsPanel({
  riskMetrics,
  isLoading,
  errorMessage,
  lookbackDays,
  onLookbackDaysChange,
  onRefresh,
}: PortfolioRiskMetricsPanelProps) {
  return (
    <Card
      title="Historical risk metrics"
      description="Review historical volatility and maximum drawdown using current persisted quantities. Currency buckets remain separate and no FX conversion is applied."
    >
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-4 rounded-md border border-border bg-surface-subtle p-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <label
              htmlFor="portfolio-risk-metrics-lookback"
              className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted"
            >
              Historical window
            </label>

            <select
              id="portfolio-risk-metrics-lookback"
              value={lookbackDays}
              onChange={(event) =>
                onLookbackDaysChange(
                  Number(event.target.value),
                )
              }
              disabled={isLoading}
              className="mt-2 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60 sm:w-44"
            >
              {LOOKBACK_OPTIONS.map((option) => (
                <option
                  key={option.value}
                  value={option.value}
                >
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <Button
            variant="ghost"
            onClick={onRefresh}
            disabled={isLoading}
          >
            {isLoading ? "Refreshing" : "Refresh risk metrics"}
          </Button>
        </div>

        {errorMessage ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-5">
            <p
              className="text-sm leading-6 text-text-secondary"
              role="alert"
            >
              {errorMessage}
            </p>
          </div>
        ) : isLoading ? (
          <div className="grid gap-5">
            {[1, 2].map((item) => (
              <div
                key={item}
                className="h-80 animate-pulse rounded-md bg-surface-muted"
              />
            ))}
          </div>
        ) : !riskMetrics ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
            <p className="text-sm font-medium text-text-primary">
              Historical risk metrics are unavailable.
            </p>
          </div>
        ) : riskMetrics.quality === "empty" ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
            <p className="text-sm font-medium text-text-primary">
              No historical risk metrics can be calculated yet.
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Add current positions and wait for historical market
              data to become available.
            </p>
          </div>
        ) : riskMetrics.currencies.length === 0 ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
            <p className="text-sm font-medium text-text-primary">
              No currency risk series are available.
            </p>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant={getQualityVariant(
                  riskMetrics.quality,
                )}
              >
                Overall quality: {riskMetrics.quality}
              </Badge>

              <span className="text-sm text-text-secondary">
                Assessed {formatTimestamp(riskMetrics.assessed_at)}
              </span>
            </div>

            <div className="grid gap-5">
              {riskMetrics.currencies.map((currency) => (
                <CurrencyRiskMetricsCard
                  key={currency.currency}
                  metrics={currency}
                />
              ))}
            </div>
          </>
        )}

        {riskMetrics && riskMetrics.quality !== "empty" && (
          <div className="border-t border-border pt-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                  Methodology
                </p>

                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  {riskMetrics.methodology}
                </p>
              </div>

              <div>
                <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                  Annualization
                </p>

                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  {riskMetrics.annualization_factor} trading
                  observations per year.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

import {
  type PortfolioCurrencyPerformanceResponse,
  type PortfolioPerformanceResponse,
} from "../../lib/portfolio-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

type PortfolioPerformancePanelProps = {
  performance: PortfolioPerformanceResponse | null;
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

const MAX_RENDERED_POINTS = 180;

function getQualityVariant(
  quality: PortfolioCurrencyPerformanceResponse["quality"],
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

function formatCurrencyValue(
  value: string | null,
  currency: string,
): string {
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
      maximumFractionDigits: 2,
    }).format(numericValue);
  } catch {
    return `${value} ${currency}`;
  }
}

function formatPeriodReturn(value: string | null): string {
  if (value === null) {
    return "—";
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  return `${new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
  }).format(numericValue * 100)}%`;
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(date);
}

function downsamplePoints(
  points: PortfolioCurrencyPerformanceResponse["points"],
): PortfolioCurrencyPerformanceResponse["points"] {
  if (points.length <= MAX_RENDERED_POINTS) {
    return points;
  }

  const sampled = [];
  const step = (points.length - 1) / (MAX_RENDERED_POINTS - 1);

  for (let index = 0; index < MAX_RENDERED_POINTS; index += 1) {
    sampled.push(points[Math.round(index * step)]);
  }

  return sampled;
}

function buildChartPoints(
  points: PortfolioCurrencyPerformanceResponse["points"],
): string {
  const renderedPoints = downsamplePoints(points);

  if (renderedPoints.length === 0) {
    return "";
  }

  const width = 640;
  const height = 220;
  const paddingX = 24;
  const paddingY = 24;

  const values = renderedPoints.map((point) => Number(point.value));

  if (values.some((value) => !Number.isFinite(value))) {
    return "";
  }

  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum || 1;

  return renderedPoints
    .map((point, index) => {
      const x =
        renderedPoints.length === 1
          ? width / 2
          : paddingX +
            (index / (renderedPoints.length - 1)) *
              (width - paddingX * 2);

      const numericValue = Number(point.value);
      const y =
        paddingY +
        ((maximum - numericValue) / range) *
          (height - paddingY * 2);

      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function PerformanceChart({
  currency,
  points,
}: {
  currency: string;
  points: PortfolioCurrencyPerformanceResponse["points"];
}) {
  if (points.length === 0) {
    return (
      <div className="flex h-44 items-center justify-center rounded-md border border-border bg-surface-subtle px-5 text-center">
        <p className="text-sm leading-6 text-text-secondary">
          No complete historical observations are available for this
          currency.
        </p>
      </div>
    );
  }

  const renderedPoints = downsamplePoints(points);
  const chartPoints = buildChartPoints(points);

  if (!chartPoints) {
    return (
      <div className="flex h-44 items-center justify-center rounded-md border border-border bg-surface-subtle px-5 text-center">
        <p className="text-sm leading-6 text-text-secondary">
          Historical values could not be rendered.
        </p>
      </div>
    );
  }

  const firstPoint = points[0];
  const lastPoint = points[points.length - 1];

  return (
    <div className="rounded-md border border-border bg-surface-subtle p-3">
      <svg
        viewBox="0 0 640 220"
        className="h-52 w-full"
        role="img"
        aria-label={`${currency} historical portfolio value`}
      >
        <title>
          {currency} historical portfolio value from{" "}
          {formatDate(firstPoint.observed_on)} to{" "}
          {formatDate(lastPoint.observed_on)}
        </title>

        <line
          x1="24"
          y1="24"
          x2="616"
          y2="24"
          className="stroke-border"
        />

        <line
          x1="24"
          y1="110"
          x2="616"
          y2="110"
          className="stroke-border"
        />

        <line
          x1="24"
          y1="196"
          x2="616"
          y2="196"
          className="stroke-border"
        />

        <polyline
          points={chartPoints}
          fill="none"
          className="stroke-brand"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {renderedPoints.length === 1 && (
          <circle
            cx="320"
            cy="110"
            r="5"
            className="fill-brand"
          />
        )}
      </svg>

      <div className="mt-2 flex items-center justify-between gap-4 text-xs text-text-muted">
        <span>{formatDate(firstPoint.observed_on)}</span>
        <span>
          {points.length.toLocaleString()} observations
        </span>
        <span>{formatDate(lastPoint.observed_on)}</span>
      </div>
    </div>
  );
}

function CurrencyPerformanceCard({
  currency,
}: {
  currency: PortfolioCurrencyPerformanceResponse;
}) {
  return (
    <div className="rounded-md border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-lg font-semibold text-text-primary">
            {currency.currency}
          </p>

          <p className="mt-1 text-sm text-text-secondary">
            {currency.position_count} position
            {currency.position_count === 1 ? "" : "s"} ·{" "}
            {currency.observation_count} complete observation
            {currency.observation_count === 1 ? "" : "s"}
          </p>
        </div>

        <Badge variant={getQualityVariant(currency.quality)}>
          {currency.quality}
        </Badge>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <PerformanceMetric
          label="Initial value"
          value={formatCurrencyValue(
            currency.initial_value,
            currency.currency,
          )}
        />

        <PerformanceMetric
          label="Latest value"
          value={formatCurrencyValue(
            currency.latest_value,
            currency.currency,
          )}
        />

        <PerformanceMetric
          label="Period return"
          value={formatPeriodReturn(currency.period_return)}
        />

        <PerformanceMetric
          label="Return observations"
          value={currency.return_count.toLocaleString()}
        />
      </div>

      <div className="mt-5">
        <PerformanceChart
          currency={currency.currency}
          points={currency.points}
        />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Observation window
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {currency.first_observed_on
              ? formatDate(currency.first_observed_on)
              : "—"}{" "}
            →{" "}
            {currency.last_observed_on
              ? formatDate(currency.last_observed_on)
              : "—"}
          </p>
        </div>

        <div>
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Data sources
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {currency.sources.length > 0
              ? currency.sources.join(", ")
              : "No source recorded"}
          </p>
        </div>
      </div>

      {currency.notes.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Method notes
          </p>

          <ul className="mt-2 space-y-1 text-sm leading-6 text-text-secondary">
            {currency.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function PerformanceMetric({
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

export function PortfolioPerformancePanel({
  performance,
  isLoading,
  errorMessage,
  lookbackDays,
  onLookbackDaysChange,
  onRefresh,
}: PortfolioPerformancePanelProps) {
  return (
    <Card
      title="Historical performance"
      description="Review the server-backed historical value path of current holdings. Currency buckets remain separate and no FX conversion is applied."
    >
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-4 rounded-md border border-border bg-surface-subtle p-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <label
              htmlFor="portfolio-performance-lookback"
              className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted"
            >
              Historical window
            </label>

            <select
              id="portfolio-performance-lookback"
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
            {isLoading ? "Refreshing" : "Refresh performance"}
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
                className="h-96 animate-pulse rounded-md bg-surface-muted"
              />
            ))}
          </div>
        ) : !performance ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
            <p className="text-sm font-medium text-text-primary">
              Historical performance is unavailable.
            </p>
          </div>
        ) : performance.quality === "empty" ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
            <p className="text-sm font-medium text-text-primary">
              No historical performance can be calculated yet.
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Add current positions and wait for historical market
              data to become available.
            </p>
          </div>
        ) : performance.currencies.length === 0 ? (
          <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
            <p className="text-sm font-medium text-text-primary">
              No currency performance series are available.
            </p>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant={getQualityVariant(
                  performance.quality,
                )}
              >
                Overall quality: {performance.quality}
              </Badge>

              <span className="text-sm text-text-secondary">
                Assessed{" "}
                {new Intl.DateTimeFormat(undefined, {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(performance.assessed_at))}
              </span>
            </div>

            <div className="grid gap-5">
              {performance.currencies.map((currency) => (
                <CurrencyPerformanceCard
                  key={currency.currency}
                  currency={currency}
                />
              ))}
            </div>
          </>
        )}

        {performance && performance.quality !== "empty" && (
          <div className="border-t border-border pt-4">
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              Methodology
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              {performance.methodology}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}

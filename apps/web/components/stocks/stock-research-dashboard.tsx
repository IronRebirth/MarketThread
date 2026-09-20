"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  fetchStockResearch,
  StockResearchApiError,
  type StockResearchBar,
  type StockResearchData,
} from "../../lib/stock-research-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

const LOOKBACK_DAYS = 365;

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function price(value: string | number | null) {
  if (value === null) return "—";
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric)
    ? numeric.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : String(value);
}

function dateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function sma(bars: StockResearchBar[], window: number) {
  if (bars.length < window) return null;
  const values = bars.slice(-window).map((bar) => Number(bar.close));
  return values.reduce((sum, value) => sum + value, 0) / window;
}

function dailyReturns(bars: StockResearchBar[]) {
  const returns: number[] = [];
  for (let index = 1; index < bars.length; index += 1) {
    const previous = Number(bars[index - 1].close);
    const current = Number(bars[index].close);
    if (
      previous > 0 &&
      Number.isFinite(previous) &&
      Number.isFinite(current)
    ) {
      returns.push(current / previous - 1);
    }
  }
  return returns;
}

function annualizedVolatility(bars: StockResearchBar[]) {
  const returns = dailyReturns(bars);
  if (returns.length < 20) return null;
  const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const variance =
    returns.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
    (returns.length - 1);
  return Math.sqrt(variance) * Math.sqrt(252);
}

function maxDrawdown(bars: StockResearchBar[]) {
  if (bars.length < 2) return null;
  let peak = Number(bars[0].close);
  let worst = 0;

  for (const bar of bars) {
    const close = Number(bar.close);
    if (!Number.isFinite(close)) continue;
    peak = Math.max(peak, close);
    if (peak > 0) worst = Math.min(worst, close / peak - 1);
  }

  return worst;
}

function TechnicalSummary({ data }: { data: StockResearchData }) {
  const latest = data.bars.at(-1);
  const latestClose = latest ? Number(latest.close) : null;
  const sma20 = sma(data.bars, 20);
  const sma50 = sma(data.bars, 50);
  const sma200 = sma(data.bars, 200);
  const volatility = annualizedVolatility(data.bars);
  const drawdown = maxDrawdown(data.bars);

  return (
    <Card
      title="Technical analysis"
      description="Deterministic indicators calculated from the persisted OHLCV bars returned by MarketThread."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Metric
          label="Latest close"
          value={latestClose === null ? "—" : price(latestClose)}
        />
        <Metric
          label="20-day SMA"
          value={sma20 === null ? "Insufficient data" : price(sma20)}
        />
        <Metric
          label="50-day SMA"
          value={sma50 === null ? "Insufficient data" : price(sma50)}
        />
        <Metric
          label="200-day SMA"
          value={sma200 === null ? "Insufficient data" : price(sma200)}
        />
        <Metric
          label="Annualized volatility"
          value={
            volatility === null
              ? "Insufficient data"
              : percent(volatility)
          }
        />
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <ResearchRow
          label="Trend context"
          value={
            latestClose !== null && sma50 !== null
              ? latestClose >= sma50
                ? "Above 50-day average"
                : "Below 50-day average"
              : "Insufficient data"
          }
        />
        <ResearchRow
          label="Maximum drawdown"
          value={drawdown === null ? "Insufficient data" : percent(drawdown)}
        />
      </div>

      <p className="mt-5 border-t border-border pt-4 text-xs leading-5 text-text-muted">
        These are descriptive historical indicators. They are not forecasts and
        do not establish a probability of future returns.
      </p>
    </Card>
  );
}

function PriceHistory({ bars }: { bars: StockResearchBar[] }) {
  const visible = bars.slice(-30);
  const values = visible
    .map((bar) => Number(bar.close))
    .filter(Number.isFinite);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;
  const range = max - min || 1;

  return (
    <Card
      title="Price history"
      description="Last 30 persisted bars in the selected research window."
    >
      {visible.length === 0 ? (
        <Unavailable text="No historical OHLCV bars are currently available." />
      ) : (
        <div className="overflow-x-auto">
          <div className="flex min-w-[680px] items-end gap-1 border-b border-border px-2 pb-2 pt-6">
            {visible.map((bar) => {
              const close = Number(bar.close);
              const height = 12 + ((close - min) / range) * 160;

              return (
                <div
                  key={`${bar.timestamp}-${bar.source}`}
                  className="group flex flex-1 flex-col items-center justify-end"
                  title={`${dateTime(bar.timestamp)} · close ${price(close)}`}
                >
                  <div
                    className="w-full min-w-1 rounded-t bg-brand/70 transition group-hover:bg-brand"
                    style={{ height }}
                  />
                </div>
              );
            })}
          </div>

          <div className="mt-3 flex justify-between text-xs text-text-muted">
            <span>{dateTime(visible[0].timestamp)}</span>
            <span>{dateTime(visible.at(-1)!.timestamp)}</span>
          </div>
        </div>
      )}
    </Card>
  );
}

export function StockResearchDashboard({
  initialSymbol,
}: {
  initialSymbol: string;
}) {
  const [data, setData] = useState<StockResearchData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      setData(await fetchStockResearch(initialSymbol, LOOKBACK_DAYS));
    } catch (error) {
      setData(null);
      setErrorMessage(
        error instanceof StockResearchApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Stock research could not be loaded.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [initialSymbol]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [load]);

  const researchSignals = useMemo(
    () =>
      [...(data?.signals ?? [])]
        .sort(
          (first, second) =>
            second.confidence - first.confidence ||
            second.risk_score - first.risk_score,
        )
        .slice(0, 6),
    [data?.signals],
  );

  if (isLoading) {
    return (
      <div className="flex flex-col gap-5">
        <Card
          title="Loading stock research"
          description="Retrieving persisted market and intelligence records."
        >
          <div className="flex flex-col gap-3">
            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="h-24 animate-pulse rounded-md bg-surface-muted"
              />
            ))}
          </div>
        </Card>
      </div>
    );
  }

  if (errorMessage || !data) {
    return (
      <div className="flex flex-col gap-6">
        <Card
          title="Stock research unavailable"
          description="The requested instrument could not be resolved from the MarketThread data layer."
        >
          <p
            className="text-sm leading-6 text-text-secondary"
            role="alert"
          >
            {errorMessage ?? "No research data is available."}
          </p>
          <div className="mt-4 flex gap-2">
            <Button onClick={() => void load()}>Try again</Button>
            <Link
              href="/stocks"
              className="inline-flex h-10 items-center rounded-md border border-border px-4 text-sm font-medium text-text-primary hover:bg-surface-subtle"
            >
              Search another stock
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  const { instrument, quote, quoteQuality, historicalQuality } = data;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Stock Research</Badge>
          <Badge variant="neutral">{instrument.exchange}</Badge>
          <Badge
            variant={
              quoteQuality?.status === "fresh" ? "positive" : "warning"
            }
          >
            Quote {quoteQuality?.status ?? "unavailable"}
          </Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="font-mono text-sm font-semibold text-brand">
              {instrument.symbol}
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              {instrument.name}
            </h1>
            <p className="mt-2 text-sm text-text-secondary">
              {instrument.exchange} · {instrument.currency} ·{" "}
              {label(instrument.asset_class)}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => void load()}>
              Refresh research
            </Button>
            <Link
              href="/stocks"
              className="inline-flex h-10 items-center rounded-md border border-border px-4 text-sm font-medium text-text-primary hover:bg-surface-subtle"
            >
              Change stock
            </Link>
          </div>
        </div>
      </header>

      <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Latest price"
          value={quote ? price(quote.price) : "Unavailable"}
        />
        <Metric
          label="Quote source"
          value={quote?.source ?? "Unavailable"}
        />
        <Metric label="Historical bars" value={String(data.bars.length)} />
        <Metric
          label="Historical coverage"
          value={
            historicalQuality
              ? percent(historicalQuality.coverage_ratio)
              : "Unavailable"
          }
        />
      </section>

      <Card
        title="Market-data quality"
        description="Freshness and coverage are displayed alongside research so missing or stale data remains visible."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <ResearchRow
            label="Latest quote"
            value={
              quoteQuality?.observed_at
                ? dateTime(quoteQuality.observed_at)
                : "Unavailable"
            }
          />
          <ResearchRow
            label="Quote age"
            value={
              quoteQuality?.age_seconds == null
                ? "Unavailable"
                : `${Math.round(quoteQuality.age_seconds)} seconds`
            }
          />
          <ResearchRow
            label="Historical status"
            value={
              historicalQuality
                ? label(historicalQuality.status)
                : "Unavailable"
            }
          />
          <ResearchRow
            label="Observed range"
            value={
              historicalQuality?.first_observed_at &&
              historicalQuality.last_observed_at
                ? `${dateTime(
                    historicalQuality.first_observed_at,
                  )} → ${dateTime(historicalQuality.last_observed_at)}`
                : "Unavailable"
            }
          />
        </div>
      </Card>

      <PriceHistory bars={data.bars} />
      <TechnicalSummary data={data} />

      <section className="grid gap-5 xl:grid-cols-2">
        <ResearchList
          title="Company impact"
          description="Persisted company-impact assessments associated with this ticker."
          empty="No persisted company-impact assessments are currently linked to this ticker."
        >
          {data.impacts.slice(0, 6).map((impact) => (
            <ResearchItem
              key={impact.impact_id}
              title={`${label(impact.direction)} · ${label(
                impact.impact_type,
              )}`}
              meta={`${percent(impact.confidence)} confidence`}
              body={impact.rationale}
            />
          ))}
        </ResearchList>

        <ResearchList
          title="Market events"
          description="Events connected to the persisted company-impact records."
          empty="No persisted market events are currently linked to this ticker."
        >
          {data.events.slice(0, 6).map((event) => (
            <ResearchItem
              key={event.event_id}
              title={event.title}
              meta={`${label(event.market_relevance)} relevance · ${percent(
                event.confidence,
              )} confidence`}
              body={event.summary}
            />
          ))}
        </ResearchList>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <ResearchList
          title="Signals"
          description="Persisted signals matching this instrument."
          empty="No persisted signals currently match this ticker."
        >
          {researchSignals.map((signal) => (
            <ResearchItem
              key={signal.signal_id}
              title={`${label(signal.opportunity)} · ${label(signal.direction)}`}
              meta={`${percent(signal.confidence)} confidence · ${percent(
                signal.risk_score,
              )} risk`}
              body={signal.rationale}
            />
          ))}
        </ResearchList>

        <ResearchList
          title="Recommendations"
          description="Research states derived from persisted signals."
          empty="No persisted recommendations currently match this ticker."
        >
          {data.recommendations.slice(0, 6).map((recommendation) => (
            <ResearchItem
              key={recommendation.recommendation_id}
              title={label(recommendation.state)}
              meta={`${percent(
                recommendation.confidence_score,
              )} confidence · ${percent(recommendation.risk_score)} risk`}
              body={recommendation.rationale}
            />
          ))}
        </ResearchList>
      </section>

      <FundamentalAnalysis fundamentals={data.fundamentals} />

      <Card title="Research interpretation" description="How to read this page.">
        <div className="grid gap-4 md:grid-cols-3">
          <Interpretation
            title="Historical context"
            description="Moving averages, volatility, and drawdown describe observed historical behavior over the available bars."
          />
          <Interpretation
            title="Evidence strength"
            description="Confidence describes support for a structured event, impact, signal, or recommendation. It is not a probability of profit."
          />
          <Interpretation
            title="No fabricated coverage"
            description="Missing quotes, incomplete history, and unavailable fundamentals remain visible instead of being replaced with placeholder values."
          />
        </div>
      </Card>
    </div>
  );
}

function FundamentalAnalysis({
  fundamentals,
}: {
  fundamentals: StockResearchData["fundamentals"];
}) {
  if (!fundamentals) {
    return (
      <Card
        title="Fundamental analysis"
        description="Fundamentals are shown only when a persisted provider-backed snapshot is available."
      >
        <Unavailable text="Fundamental metrics are currently unavailable for this instrument. MarketThread does not substitute estimates or fabricated values." />
      </Card>
    );
  }

  const metrics = [
    ["Revenue growth", fundamentals.revenue_growth, true],
    ["Earnings growth", fundamentals.earnings_growth, true],
    ["Gross margin", fundamentals.gross_margin, true],
    ["Operating margin", fundamentals.operating_margin, true],
    ["Net margin", fundamentals.net_margin, true],
    ["ROE", fundamentals.roe, true],
    ["ROIC", fundamentals.roic, true],
    ["Debt / equity", fundamentals.debt_to_equity, false],
    ["Debt / EBITDA", fundamentals.debt_to_ebitda, false],
    ["Operating cash flow", fundamentals.operating_cash_flow, false],
    ["Free cash flow", fundamentals.free_cash_flow, false],
    ["P/E", fundamentals.pe_ratio, false],
    ["P/S", fundamentals.ps_ratio, false],
    ["EV / EBITDA", fundamentals.ev_to_ebitda, false],
    ["Dividend yield", fundamentals.dividend_yield, true],
  ] as const;

  return (
    <Card
      title="Fundamental analysis"
      description={`Persisted provider snapshot for ${fundamentals.period_end} · source ${fundamentals.source}`}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {metrics.map(([name, value, isPercent]) => (
          <div
            key={name}
            className="rounded-md border border-border bg-surface-subtle p-4"
          >
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              {name}
            </p>
            <p className="mt-2 text-lg font-semibold text-text-primary">
              {value === null
                ? "Unavailable"
                : isPercent
                  ? percent(Number(value))
                  : price(value)}
            </p>
          </div>
        ))}
      </div>

      <p className="mt-5 border-t border-border pt-4 text-xs leading-5 text-text-muted">
        Fundamental values are provider-supplied observations for the stated
        reporting period. Missing metrics remain unavailable rather than being
        inferred.
      </p>
    </Card>
  );
}

function ResearchList({
  title,
  description,
  empty,
  children,
}: {
  title: string;
  description: string;
  empty: string;
  children: React.ReactNode;
}) {
  const hasChildren = Array.isArray(children)
    ? children.length > 0
    : Boolean(children);

  return (
    <Card title={title} description={description}>
      {hasChildren ? (
        <div className="flex flex-col divide-y divide-border">{children}</div>
      ) : (
        <Unavailable text={empty} />
      )}
    </Card>
  );
}

function ResearchItem({
  title,
  meta,
  body,
}: {
  title: string;
  meta: string;
  body: string;
}) {
  return (
    <article className="py-4 first:pt-0 last:pb-0">
      <p className="text-sm font-semibold text-text-primary">{title}</p>
      <p className="mt-1 text-xs text-text-muted">{meta}</p>
      <p className="mt-2 text-sm leading-6 text-text-secondary">{body}</p>
    </article>
  );
}

function ResearchRow({
  label: rowLabel,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-border bg-surface-subtle px-4 py-3">
      <span className="text-sm text-text-secondary">{rowLabel}</span>
      <span className="text-right text-sm font-medium text-text-primary">
        {value}
      </span>
    </div>
  );
}

function Metric({
  label: metricLabel,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <Card>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {metricLabel}
      </p>
      <p className="mt-2 break-words text-2xl font-semibold tracking-tight text-text-primary">
        {value}
      </p>
    </Card>
  );
}

function Unavailable({ text }: { text: string }) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle p-5">
      <p className="text-sm leading-6 text-text-secondary">{text}</p>
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

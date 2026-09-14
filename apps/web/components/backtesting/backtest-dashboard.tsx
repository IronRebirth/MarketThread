"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchBacktestPerformanceReport } from "../../lib/backtest-api";
import { developmentBacktestExecution } from "../../lib/backtest-preview";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

type Report = Awaited<
  ReturnType<typeof fetchBacktestPerformanceReport>
>;

function QualityBadge({ state }: { state: string }) {
  const variant =
    state === "reliable"
      ? "positive"
      : state === "limited_evidence"
        ? "warning"
        : "neutral";

  const label = state.replaceAll("_", " ");

  return <Badge variant={variant}>{label}</Badge>;
}

function MetricValue({
  value,
  label,
}: {
  value: string;
  label: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <p className="mt-1 text-xl font-semibold tracking-tight text-text-primary">
        {value}
      </p>
    </div>
  );
}

function formatPercentage(value: number | null) {
  if (value === null) {
    return "—";
  }

  return `${value.toFixed(2)}%`;
}

function formatQualityState(state: string) {
  return state.replaceAll("_", " ");
}

export function BacktestDashboard() {
  const [report, setReport] = useState<Report | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextReport = await fetchBacktestPerformanceReport(
        developmentBacktestExecution,
      );

      setReport(nextReport);
    } catch (error) {
      setReport(null);
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "The backtest report could not be loaded.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadReport();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadReport]);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Backtesting</Badge>
          <Badge variant="neutral">API connected</Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Backtest performance
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Evaluate historical signal performance across time horizons,
              recommendation states, signal strength, and evidence quality.
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() => void loadReport()}
            disabled={isLoading}
          >
            {isLoading ? "Loading report" : "Refresh report"}
          </Button>
        </div>
      </header>

      {errorMessage && (
        <Card
          title="Backtest report unavailable"
          description="The dashboard could not retrieve the performance report from the API."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button onClick={() => void loadReport()}>Try again</Button>
            </div>
          </div>
        </Card>
      )}

      {isLoading && (
        <Card
          title="Loading backtest report"
          description="Retrieving performance and evidence-quality metrics from the MarketThread API."
        >
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="h-16 animate-pulse rounded-md bg-surface-muted"
              />
            ))}
          </div>
        </Card>
      )}

      {!isLoading && !errorMessage && report && (
        <>
          <Card
            title="Current analysis"
            description="Metrics are returned by the MarketThread backtest performance API."
          >
            <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
              <MetricValue
                label="Evaluations"
                value={String(report.total_evaluations)}
              />

              <MetricValue
                label="Directional accuracy"
                value={formatPercentage(report.directional_accuracy)}
              />

              <MetricValue
                label="Average return"
                value={formatPercentage(
                  report.average_forward_return_pct,
                )}
              />

              <MetricValue
                label="Relative return"
                value={formatPercentage(
                  report.average_relative_return_pct,
                )}
              />
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-5">
              <QualityBadge state={report.quality_state} />

              <span className="text-sm text-text-secondary">
                {report.valid_evaluations} valid evaluations
              </span>

              <span className="text-text-muted">•</span>

              <span className="text-sm text-text-secondary">
                {report.quality_coverage_ratio !== null
                  ? `${(report.quality_coverage_ratio * 100).toFixed(1)}% coverage`
                  : "Coverage unavailable"}
              </span>
            </div>
          </Card>

          <section className="grid gap-6 xl:grid-cols-[1.45fr_0.55fr]">
            <Card
              title="Performance by horizon"
              description="Actual horizon-specific evaluations returned by the API."
            >
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left">
                  <thead>
                    <tr className="border-b border-border text-xs uppercase tracking-[0.08em] text-text-muted">
                      <th className="px-2 py-3 font-medium">Horizon</th>
                      <th className="px-2 py-3 font-medium">
                        Evaluations
                      </th>
                      <th className="px-2 py-3 font-medium">Accuracy</th>
                      <th className="px-2 py-3 font-medium">
                        Forward return
                      </th>
                      <th className="px-2 py-3 font-medium">
                        Relative return
                      </th>
                      <th className="px-2 py-3 font-medium">Quality</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-border">
                    {report.by_horizon.summaries.map((item) => (
                      <tr key={item.state}>
                        <td className="px-2 py-4">
                          <span className="font-semibold text-text-primary">
                            {item.state.toUpperCase()}
                          </span>
                        </td>

                        <td className="px-2 py-4 text-sm text-text-secondary">
                          {item.evaluation_count}
                        </td>

                        <td className="px-2 py-4 text-sm font-medium text-text-primary">
                          {formatPercentage(item.directional_accuracy)}
                        </td>

                        <td className="px-2 py-4 text-sm font-medium text-positive">
                          {formatPercentage(
                            item.average_forward_return_pct,
                          )}
                        </td>

                        <td className="px-2 py-4 text-sm font-medium text-positive">
                          {formatPercentage(
                            item.average_relative_return_pct,
                          )}
                        </td>

                        <td className="px-2 py-4">
                          {item.quality_state ? (
                            <QualityBadge state={item.quality_state} />
                          ) : (
                            <Badge variant="neutral">
                              unavailable
                            </Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card
              title="Evidence quality"
              description="Quality reflects the amount and coverage of historical evidence."
            >
              <div className="flex flex-col gap-5">
                <div>
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-sm text-text-secondary">
                      Evaluation coverage
                    </span>

                    <span className="text-sm font-semibold text-text-primary">
                      {report.quality_coverage_ratio !== null
                        ? `${(
                            report.quality_coverage_ratio * 100
                          ).toFixed(1)}%`
                        : "—"}
                    </span>
                  </div>

                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted">
                    <div
                      className="h-full rounded-full bg-brand"
                      style={{
                        width: `${
                          (report.quality_coverage_ratio ?? 0) * 100
                        }%`,
                      }}
                    />
                  </div>
                </div>

                <div className="rounded-md border border-border bg-surface-subtle p-4">
                  <div className="flex items-center gap-2">
                    <QualityBadge state={report.quality_state} />
                  </div>

                  <p className="mt-3 text-sm leading-6 text-text-secondary">
                    {report.quality_state === "reliable"
                      ? "The available evaluation sample meets the configured quality threshold."
                      : report.quality_state === "limited_evidence"
                        ? "The result is usable but the available evidence remains limited."
                        : "There is not enough historical evidence to support a reliable interpretation."}
                  </p>
                </div>

                {report.quality_warnings.length > 0 && (
                  <div>
                    <p className="text-sm font-semibold text-text-primary">
                      Warnings
                    </p>

                    <div className="mt-2 flex flex-col gap-2">
                      {report.quality_warnings.map((warning) => (
                        <div
                          key={warning}
                          className="rounded-md bg-warning-soft px-3 py-2 text-sm text-warning"
                        >
                          {formatQualityState(warning)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">
                      Valid evaluations
                    </span>

                    <span className="font-medium text-text-primary">
                      {report.valid_evaluations}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">
                      Rejected evaluations
                    </span>

                    <span className="font-medium text-text-primary">
                      {report.rejected_evaluations}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          </section>

          <section className="grid gap-6 xl:grid-cols-2">
            <Card
              title="By signal strength"
              description="Historical outcomes grouped by signal strength."
            >
              <BreakdownTable
                summaries={report.by_signal_strength.summaries}
              />
            </Card>

            <Card
              title="By recommendation state"
              description="Historical outcomes grouped by recommendation state."
            >
              <BreakdownTable
                summaries={report.by_recommendation_state.summaries}
              />
            </Card>
          </section>

          <Card
            title="Interpretation"
            description="How MarketThread should treat the displayed results."
          >
            <div className="grid gap-4 md:grid-cols-3">
              <Interpretation
                title="Performance"
                description="Describes historical observed outcomes. It does not establish future returns or causality."
              />

              <Interpretation
                title="Confidence"
                description="Represents evidence support for a signal, not the probability that an investment will be profitable."
              />

              <Interpretation
                title="Quality"
                description="Indicates whether the amount and coverage of evidence are strong enough to support interpretation."
              />
            </div>
          </Card>

          <p className="text-xs text-text-muted">
            Development note: this dashboard currently sends a typed
            development execution fixture to the live report API. A
            persisted backtest-run endpoint will replace that fixture.
          </p>
        </>
      )}
    </div>
  );
}

function BreakdownTable({
  summaries,
}: {
  summaries: Report["by_signal_strength"]["summaries"];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-left">
        <thead>
          <tr className="border-b border-border text-xs uppercase tracking-[0.08em] text-text-muted">
            <th className="px-2 py-3 font-medium">State</th>
            <th className="px-2 py-3 font-medium">Evaluations</th>
            <th className="px-2 py-3 font-medium">Accuracy</th>
            <th className="px-2 py-3 font-medium">Relative return</th>
          </tr>
        </thead>

        <tbody className="divide-y divide-border">
          {summaries.map((item) => (
            <tr key={String(item.state)}>
              <td className="px-2 py-4 text-sm font-medium text-text-primary">
                {String(item.state)}
              </td>

              <td className="px-2 py-4 text-sm text-text-secondary">
                {item.evaluation_count}
              </td>

              <td className="px-2 py-4 text-sm text-text-primary">
                {formatPercentage(item.directional_accuracy)}
              </td>

              <td className="px-2 py-4 text-sm font-medium text-positive">
                {formatPercentage(item.average_relative_return_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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

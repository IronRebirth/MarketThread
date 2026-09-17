"use client";

import { useCallback, useEffect, useState } from "react";

import {
  BacktestApiError,
  fetchBacktestEvaluations,
  fetchBacktestPerformanceReportById,
  fetchBacktestProvenance,
  fetchBacktestRuns,
  fetchLatestBacktestPerformanceReport,
  type BacktestEvaluationAudit,
  type BacktestPerformanceReport,
  type BacktestProvenance,
  type BacktestRunResponse,
} from "../../lib/backtest-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { BacktestRunConfigurationCard } from "./backtest-run-configuration";

type Report = BacktestPerformanceReport;

const EVALUATIONS_PAGE_SIZE = 50;

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

function formatConfidence(value: number | null) {
  if (value === null) {
    return "—";
  }

  return value.toFixed(3);
}

function formatQualityState(state: string) {
  return state.replaceAll("_", " ");
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

function formatStage(stage: BacktestProvenance["stage"]) {
  return stage.replaceAll("_", " ");
}

function formatRunLabel(run: BacktestRunResponse) {
  return `${formatTimestamp(run.completed_at)} · ${run.evaluation_count} evaluations`;
}

function getAlternativeRunId(
  runs: BacktestRunResponse[],
  excludedId: string | null,
) {
  return (
    runs.find((run) => run.backtest_id !== excludedId)?.backtest_id ?? null
  );
}

function getEvaluationStatusVariant(status: string) {
  if (status === "valid" || status === "accepted") {
    return "positive" as const;
  }

  if (
    status === "rejected" ||
    status === "invalid" ||
    status === "temporal_error"
  ) {
    return "warning" as const;
  }

  return "neutral" as const;
}

export function BacktestDashboard() {
  const [report, setReport] = useState<Report | null>(null);
  const [provenance, setProvenance] = useState<BacktestProvenance | null>(
    null,
  );

  const [comparisonReport, setComparisonReport] =
    useState<BacktestPerformanceReport | null>(null);
  const [comparisonProvenance, setComparisonProvenance] =
    useState<BacktestProvenance | null>(null);

  const [evaluations, setEvaluations] = useState<BacktestEvaluationAudit[]>([]);
  const [totalEvaluations, setTotalEvaluations] = useState(0);
  const [evaluationOffset, setEvaluationOffset] = useState(0);

  const [runs, setRuns] = useState<BacktestRunResponse[]>([]);
  const [totalRuns, setTotalRuns] = useState(0);

  const [selectedBacktestId, setSelectedBacktestId] = useState<string | null>(
    null,
  );
  const [comparisonRunId, setComparisonRunId] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isRunLoading, setIsRunLoading] = useState(false);
  const [isProvenanceLoading, setIsProvenanceLoading] = useState(false);
  const [isComparisonLoading, setIsComparisonLoading] = useState(false);
  const [isEvaluationsLoading, setIsEvaluationsLoading] = useState(false);

  const [provenanceUnavailable, setProvenanceUnavailable] = useState(false);
  const [comparisonProvenanceUnavailable, setComparisonProvenanceUnavailable] =
    useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [historyErrorMessage, setHistoryErrorMessage] = useState<string | null>(
    null,
  );
  const [provenanceErrorMessage, setProvenanceErrorMessage] = useState<
    string | null
  >(null);
  const [comparisonErrorMessage, setComparisonErrorMessage] = useState<
    string | null
  >(null);
  const [evaluationsErrorMessage, setEvaluationsErrorMessage] = useState<
    string | null
  >(null);

  const loadProvenance = useCallback(async (backtestId: string) => {
    setIsProvenanceLoading(true);
    setProvenance(null);
    setProvenanceUnavailable(false);
    setProvenanceErrorMessage(null);

    try {
      const nextProvenance = await fetchBacktestProvenance(backtestId);

      setProvenance(nextProvenance);
    } catch (error) {
      if (error instanceof BacktestApiError && error.status === 404) {
        setProvenanceUnavailable(true);
      } else {
        setProvenanceErrorMessage(
          error instanceof Error
            ? error.message
            : "The backtest provenance could not be loaded.",
        );
      }
    } finally {
      setIsProvenanceLoading(false);
    }
  }, []);

  const loadEvaluations = useCallback(
    async (backtestId: string, offset = 0) => {
      setIsEvaluationsLoading(true);
      setEvaluationsErrorMessage(null);

      try {
        const result = await fetchBacktestEvaluations(
          backtestId,
          EVALUATIONS_PAGE_SIZE,
          offset,
        );

        setEvaluations(result.evaluations);
        setTotalEvaluations(result.total);
        setEvaluationOffset(result.offset);
      } catch (error) {
        setEvaluations([]);
        setTotalEvaluations(0);
        setEvaluationOffset(0);
        setEvaluationsErrorMessage(
          error instanceof Error
            ? error.message
            : "The backtest evaluations could not be loaded.",
        );
      } finally {
        setIsEvaluationsLoading(false);
      }
    },
    [],
  );

  const loadComparison = useCallback(async (backtestId: string) => {
    setIsComparisonLoading(true);
    setComparisonErrorMessage(null);
    setComparisonReport(null);
    setComparisonProvenance(null);
    setComparisonProvenanceUnavailable(false);

    const [reportResult, provenanceResult] = await Promise.allSettled([
      fetchBacktestPerformanceReportById(backtestId),
      fetchBacktestProvenance(backtestId),
    ]);

    if (reportResult.status === "fulfilled") {
      setComparisonReport(reportResult.value);
    } else {
      setComparisonErrorMessage(
        reportResult.reason instanceof Error
          ? reportResult.reason.message
          : "The comparison backtest could not be loaded.",
      );
    }

    if (provenanceResult.status === "fulfilled") {
      setComparisonProvenance(provenanceResult.value);
    } else if (
      provenanceResult.reason instanceof BacktestApiError &&
      provenanceResult.reason.status === 404
    ) {
      setComparisonProvenanceUnavailable(true);
    } else {
      setComparisonErrorMessage((currentMessage) => {
        if (currentMessage) {
          return currentMessage;
        }

        return provenanceResult.reason instanceof Error
          ? provenanceResult.reason.message
          : "The comparison provenance could not be loaded.";
      });
    }

    setIsComparisonLoading(false);
  }, []);

  const loadRun = useCallback(
    async (backtestId: string) => {
      setIsRunLoading(true);
      setErrorMessage(null);
      setSelectedBacktestId(backtestId);

      let nextComparisonId = comparisonRunId;

      if (nextComparisonId === backtestId) {
        nextComparisonId = getAlternativeRunId(runs, backtestId);
        setComparisonRunId(nextComparisonId);
      }

      try {
        const nextReport =
          await fetchBacktestPerformanceReportById(backtestId);

        setReport(nextReport);

        await Promise.all([
          loadProvenance(backtestId),
          loadEvaluations(backtestId),
        ]);

        if (nextComparisonId) {
          await loadComparison(nextComparisonId);
        } else {
          setComparisonReport(null);
          setComparisonProvenance(null);
          setComparisonProvenanceUnavailable(false);
          setComparisonErrorMessage(null);
        }
      } catch (error) {
        setReport(null);
        setProvenance(null);
        setProvenanceUnavailable(false);
        setProvenanceErrorMessage(null);
        setEvaluations([]);
        setTotalEvaluations(0);
        setEvaluationOffset(0);
        setEvaluationsErrorMessage(null);

        setErrorMessage(
          error instanceof Error
            ? error.message
            : "The selected backtest could not be loaded.",
        );
      } finally {
        setIsRunLoading(false);
      }
    },
    [
      comparisonRunId,
      loadComparison,
      loadEvaluations,
      loadProvenance,
      runs,
    ],
  );

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    setHistoryErrorMessage(null);
    setReport(null);
    setRuns([]);
    setTotalRuns(0);
    setSelectedBacktestId(null);
    setComparisonRunId(null);
    setComparisonReport(null);
    setComparisonProvenance(null);
    setComparisonProvenanceUnavailable(false);
    setComparisonErrorMessage(null);
    setProvenance(null);
    setProvenanceUnavailable(false);
    setProvenanceErrorMessage(null);
    setEvaluations([]);
    setTotalEvaluations(0);
    setEvaluationOffset(0);
    setEvaluationsErrorMessage(null);

    const [latestResult, historyResult] = await Promise.allSettled([
      fetchLatestBacktestPerformanceReport(),
      fetchBacktestRuns(),
    ]);

    let latestReport: BacktestPerformanceReport | null = null;
    let nextRuns: BacktestRunResponse[] = [];
    let nextComparisonId: string | null = null;

    if (latestResult.status === "fulfilled") {
      latestReport = latestResult.value;
      setReport(latestReport);
      setSelectedBacktestId(latestReport.backtest_id);
    } else {
      setErrorMessage(
        latestResult.reason instanceof Error
          ? latestResult.reason.message
          : "The latest backtest report could not be loaded.",
      );
    }

    if (historyResult.status === "fulfilled") {
      nextRuns = historyResult.value.runs;
      setRuns(nextRuns);
      setTotalRuns(historyResult.value.total);

      if (latestReport) {
        nextComparisonId = getAlternativeRunId(
          nextRuns,
          latestReport.backtest_id,
        );

        setComparisonRunId(nextComparisonId);
      }
    } else {
      setHistoryErrorMessage(
        historyResult.reason instanceof Error
          ? historyResult.reason.message
          : "The backtest run history could not be loaded.",
      );
    }

    setIsLoading(false);

    if (latestReport) {
      await Promise.all([
        loadProvenance(latestReport.backtest_id),
        loadEvaluations(latestReport.backtest_id),
      ]);

      if (nextComparisonId) {
        await loadComparison(nextComparisonId);
      }
    }
  }, [loadComparison, loadEvaluations, loadProvenance]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadDashboard();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadDashboard]);

  const handleRunSelection = (backtestId: string) => {
    if (backtestId === selectedBacktestId || isRunLoading) {
      return;
    }

    void loadRun(backtestId);
  };

  const handleComparisonSelection = (backtestId: string) => {
    if (
      backtestId === selectedBacktestId ||
      backtestId === comparisonRunId ||
      isComparisonLoading
    ) {
      return;
    }

    setComparisonRunId(backtestId);
    void loadComparison(backtestId);
  };

  const handlePreviousEvaluations = () => {
    if (evaluationOffset === 0 || isEvaluationsLoading || !selectedBacktestId) {
      return;
    }

    void loadEvaluations(
      selectedBacktestId,
      Math.max(0, evaluationOffset - EVALUATIONS_PAGE_SIZE),
    );
  };

  const handleNextEvaluations = () => {
    if (
      isEvaluationsLoading ||
      !selectedBacktestId ||
      evaluationOffset + evaluations.length >= totalEvaluations
    ) {
      return;
    }

    void loadEvaluations(
      selectedBacktestId,
      evaluationOffset + EVALUATIONS_PAGE_SIZE,
    );
  };

  const selectedRun =
    runs.find((run) => run.backtest_id === selectedBacktestId) ?? null;

  const comparisonRun =
    runs.find((run) => run.backtest_id === comparisonRunId) ?? null;

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
              recommendation states, signal strength, evidence quality,
              persisted runs, and evaluation-level audit records.
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() => void loadDashboard()}
            disabled={
              isLoading ||
              isRunLoading ||
              isComparisonLoading ||
              isEvaluationsLoading
            }
          >
            {isLoading ? "Loading report" : "Refresh report"}
          </Button>
        </div>
      </header>

      {historyErrorMessage && (
        <Card
          title="Run history unavailable"
          description="The current report may still be available even though historical run metadata could not be retrieved."
        >
          <p className="text-sm leading-6 text-text-secondary">
            {historyErrorMessage}
          </p>
        </Card>
      )}

      {!isLoading && runs.length > 0 && (
        <Card
          title="Run history"
          description="Select a persisted backtest execution to inspect its report, provenance, and evaluation audit."
        >
          <div className="flex flex-col gap-5">
            <label
              htmlFor="backtest-run"
              className="text-sm font-medium text-text-primary"
            >
              Selected run
            </label>

            <select
              id="backtest-run"
              value={selectedBacktestId ?? ""}
              onChange={(event) => handleRunSelection(event.target.value)}
              disabled={isRunLoading}
              className="w-full rounded-md border border-border bg-surface-subtle px-3 py-2.5 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {runs.map((run) => (
                <option key={run.backtest_id} value={run.backtest_id}>
                  {formatRunLabel(run)}
                </option>
              ))}
            </select>

            {selectedBacktestId && (
              <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
                {runs.find(
                  (run) => run.backtest_id === selectedBacktestId,
                )?.valid ? (
                  <Badge variant="positive">Valid run</Badge>
                ) : (
                  <Badge variant="warning">Run contains rejections</Badge>
                )}

                <span className="text-sm text-text-secondary">
                  {selectedBacktestId}
                </span>
              </div>
            )}

            <p className="text-xs leading-5 text-text-muted">
              Showing {runs.length} of {totalRuns} persisted runs.
            </p>
          </div>
        </Card>
      )}

      {!isLoading && selectedRun && (
        <BacktestRunConfigurationCard run={selectedRun} />
      )}

      {!isLoading && runs.length > 1 && selectedBacktestId && (
        <Card
          title="Compare runs"
          description="Compare the selected execution with another persisted historical run."
        >
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <label
                htmlFor="backtest-comparison-run"
                className="text-sm font-medium text-text-primary"
              >
                Compare selected run with
              </label>

              <select
                id="backtest-comparison-run"
                value={comparisonRunId ?? ""}
                onChange={(event) =>
                  handleComparisonSelection(event.target.value)
                }
                disabled={isComparisonLoading}
                className="w-full rounded-md border border-border bg-surface-subtle px-3 py-2.5 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {runs
                  .filter((run) => run.backtest_id !== selectedBacktestId)
                  .map((run) => (
                    <option key={run.backtest_id} value={run.backtest_id}>
                      {formatRunLabel(run)}
                    </option>
                  ))}
              </select>
            </div>

            {isComparisonLoading && (
              <div className="grid gap-4 xl:grid-cols-2">
                {[1, 2].map((item) => (
                  <div
                    key={item}
                    className="h-48 animate-pulse rounded-md bg-surface-muted"
                  />
                ))}
              </div>
            )}

            {!isComparisonLoading && comparisonErrorMessage && (
              <div className="rounded-md border border-border bg-surface-subtle p-4">
                <p className="text-sm leading-6 text-text-secondary">
                  {comparisonErrorMessage}
                </p>
              </div>
            )}

            {!isComparisonLoading &&
              !comparisonErrorMessage &&
              report &&
              comparisonReport &&
              comparisonRun && (
                <RunComparison
                  selectedRun={selectedRun}
                  selectedReport={report}
                  selectedProvenance={provenance}
                  comparisonRun={comparisonRun}
                  comparisonReport={comparisonReport}
                  comparisonProvenance={comparisonProvenance}
                  comparisonProvenanceUnavailable={
                    comparisonProvenanceUnavailable
                  }
                />
              )}
          </div>
        </Card>
      )}

      {errorMessage && (
        <Card
          title="Backtest report unavailable"
          description="The dashboard could not retrieve the requested performance report from the API."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button onClick={() => void loadDashboard()}>Try again</Button>
            </div>
          </div>
        </Card>
      )}

      {(isLoading || isRunLoading) && (
        <Card
          title={
            isRunLoading
              ? "Loading selected backtest"
              : "Loading backtest report"
          }
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

      {!isLoading && !isRunLoading && !errorMessage && report && (
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

          <EvaluationAuditCard
            evaluations={evaluations}
            total={totalEvaluations}
            offset={evaluationOffset}
            isLoading={isEvaluationsLoading}
            errorMessage={evaluationsErrorMessage}
            onPrevious={handlePreviousEvaluations}
            onNext={handleNextEvaluations}
          />

          <ProvenanceCard
            provenance={provenance}
            isLoading={isProvenanceLoading}
            unavailable={provenanceUnavailable}
            errorMessage={provenanceErrorMessage}
          />

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
                title="Audit"
                description="Shows persisted evaluation records used to construct aggregate backtest results."
              />
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function EvaluationAuditCard({
  evaluations,
  total,
  offset,
  isLoading,
  errorMessage,
  onPrevious,
  onNext,
}: {
  evaluations: BacktestEvaluationAudit[];
  total: number;
  offset: number;
  isLoading: boolean;
  errorMessage: string | null;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <Card
      title="Evaluation audit"
      description="Persisted evaluation-level records for the selected backtest run."
    >
      <div className="flex flex-col gap-5">
        {isLoading && (
          <div className="overflow-hidden rounded-md border border-border">
            <div className="h-64 animate-pulse bg-surface-muted" />
          </div>
        )}

        {!isLoading && errorMessage && (
          <div className="rounded-md border border-border bg-surface-subtle p-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>
          </div>
        )}

        {!isLoading && !errorMessage && evaluations.length === 0 && (
          <div className="rounded-md border border-border bg-surface-subtle p-6">
            <p className="text-sm font-medium text-text-primary">
              No evaluation records are available.
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              The selected backtest does not currently have persisted
              evaluation-level records.
            </p>
          </div>
        )}

        {!isLoading && !errorMessage && evaluations.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1500px] text-left">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-[0.08em] text-text-muted">
                    <th className="px-2 py-3 font-medium">Fold</th>
                    <th className="px-2 py-3 font-medium">Created</th>
                    <th className="px-2 py-3 font-medium">Status</th>
                    <th className="px-2 py-3 font-medium">Temporal</th>
                    <th className="px-2 py-3 font-medium">Signal</th>
                    <th className="px-2 py-3 font-medium">Event</th>
                    <th className="px-2 py-3 font-medium">Direction</th>
                    <th className="px-2 py-3 font-medium">Observed</th>
                    <th className="px-2 py-3 font-medium">Strength</th>
                    <th className="px-2 py-3 font-medium">Recommendation</th>
                    <th className="px-2 py-3 font-medium">Confidence</th>
                    <th className="px-2 py-3 font-medium">Horizon</th>
                    <th className="px-2 py-3 font-medium">Forward return</th>
                    <th className="px-2 py-3 font-medium">Relative return</th>
                    <th className="px-2 py-3 font-medium">Correct</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-border">
                  {evaluations.map((evaluation) => (
                    <EvaluationAuditRow
                      key={evaluation.evaluation_id}
                      evaluation={evaluation}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-text-secondary">
                Showing {offset + 1}–{offset + evaluations.length} of {total}{" "}
                evaluations.
              </p>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={onPrevious}
                  disabled={offset === 0}
                >
                  Previous
                </Button>

                <Button
                  variant="secondary"
                  onClick={onNext}
                  disabled={offset + evaluations.length >= total}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

function EvaluationAuditRow({
  evaluation,
}: {
  evaluation: BacktestEvaluationAudit;
}) {
  return (
    <tr>
      <td className="px-2 py-4 text-sm font-medium text-text-primary">
        {evaluation.fold_number}
      </td>

      <td className="whitespace-nowrap px-2 py-4 text-sm text-text-secondary">
        {formatTimestamp(evaluation.signal_created_at)}
      </td>

      <td className="px-2 py-4">
        <Badge variant={getEvaluationStatusVariant(evaluation.status)}>
          {formatQualityState(evaluation.status)}
        </Badge>
      </td>

      <td className="px-2 py-4">
        {evaluation.temporal_error ? (
          <span
            className="text-sm font-medium text-warning"
            title={evaluation.temporal_error}
          >
            {formatQualityState(evaluation.temporal_error)}
          </span>
        ) : (
          <span className="text-sm text-text-secondary">none</span>
        )}
      </td>

      <td className="px-2 py-4">
        <code className="text-xs text-text-secondary">
          {evaluation.signal_id}
        </code>
      </td>

      <td className="px-2 py-4">
        <code className="text-xs text-text-secondary">
          {evaluation.event_id}
        </code>
      </td>

      <td className="px-2 py-4 text-sm text-text-primary">
        {formatQualityState(evaluation.signal_direction)}
      </td>

      <td className="px-2 py-4 text-sm text-text-secondary">
        {formatQualityState(evaluation.observed_direction)}
      </td>

      <td className="px-2 py-4 text-sm text-text-primary">
        {formatQualityState(evaluation.signal_strength)}
      </td>

      <td className="px-2 py-4 text-sm text-text-primary">
        {formatQualityState(evaluation.recommendation_state)}
      </td>

      <td className="px-2 py-4 text-sm text-text-primary">
        {formatConfidence(evaluation.signal_confidence)}
      </td>

      <td className="px-2 py-4 text-sm font-medium text-text-primary">
        {evaluation.horizon ?? "—"}
      </td>

      <td className="px-2 py-4 text-sm text-text-primary">
        {formatPercentage(evaluation.forward_return_pct)}
      </td>

      <td className="px-2 py-4 text-sm text-text-primary">
        {formatPercentage(evaluation.relative_return_pct)}
      </td>

      <td className="px-2 py-4">
        {evaluation.direction_correct === null ? (
          <span className="text-sm text-text-muted">—</span>
        ) : evaluation.direction_correct ? (
          <Badge variant="positive">yes</Badge>
        ) : (
          <Badge variant="warning">no</Badge>
        )}
      </td>
    </tr>
  );
}

function RunComparison({
  selectedRun,
  selectedReport,
  selectedProvenance,
  comparisonRun,
  comparisonReport,
  comparisonProvenance,
  comparisonProvenanceUnavailable,
}: {
  selectedRun: BacktestRunResponse | null;
  selectedReport: BacktestPerformanceReport;
  selectedProvenance: BacktestProvenance | null;
  comparisonRun: BacktestRunResponse;
  comparisonReport: BacktestPerformanceReport;
  comparisonProvenance: BacktestProvenance | null;
  comparisonProvenanceUnavailable: boolean;
}) {
  const horizonStates = Array.from(
    new Set([
      ...selectedReport.by_horizon.summaries.map((item) => item.state),
      ...comparisonReport.by_horizon.summaries.map((item) => item.state),
    ]),
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-5 xl:grid-cols-2">
        <ComparisonPanel
          title="Selected run"
          run={selectedRun}
          report={selectedReport}
          provenance={selectedProvenance}
        />

        <ComparisonPanel
          title="Compared run"
          run={comparisonRun}
          report={comparisonReport}
          provenance={comparisonProvenance}
          provenanceUnavailable={comparisonProvenanceUnavailable}
        />
      </div>

      <div className="border-t border-border pt-6">
        <div className="flex flex-col gap-4">
          <div>
            <p className="text-sm font-semibold text-text-primary">
              Horizon comparison
            </p>

            <p className="mt-1 text-sm leading-6 text-text-secondary">
              Side-by-side historical observations for matching horizons.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-[0.08em] text-text-muted">
                  <th className="px-2 py-3 font-medium">Horizon</th>
                  <th className="px-2 py-3 font-medium">
                    Selected evaluations
                  </th>
                  <th className="px-2 py-3 font-medium">
                    Compared evaluations
                  </th>
                  <th className="px-2 py-3 font-medium">
                    Selected accuracy
                  </th>
                  <th className="px-2 py-3 font-medium">
                    Compared accuracy
                  </th>
                  <th className="px-2 py-3 font-medium">
                    Selected relative return
                  </th>
                  <th className="px-2 py-3 font-medium">
                    Compared relative return
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border">
                {horizonStates.map((state) => {
                  const selectedSummary =
                    selectedReport.by_horizon.summaries.find(
                      (item) => item.state === state,
                    );

                  const comparisonSummary =
                    comparisonReport.by_horizon.summaries.find(
                      (item) => item.state === state,
                    );

                  return (
                    <tr key={state}>
                      <td className="px-2 py-4">
                        <span className="font-semibold text-text-primary">
                          {state.toUpperCase()}
                        </span>
                      </td>

                      <td className="px-2 py-4 text-sm text-text-secondary">
                        {selectedSummary?.evaluation_count ?? "—"}
                      </td>

                      <td className="px-2 py-4 text-sm text-text-secondary">
                        {comparisonSummary?.evaluation_count ?? "—"}
                      </td>

                      <td className="px-2 py-4 text-sm text-text-primary">
                        {formatPercentage(
                          selectedSummary?.directional_accuracy ?? null,
                        )}
                      </td>

                      <td className="px-2 py-4 text-sm text-text-primary">
                        {formatPercentage(
                          comparisonSummary?.directional_accuracy ?? null,
                        )}
                      </td>

                      <td className="px-2 py-4 text-sm text-text-primary">
                        {formatPercentage(
                          selectedSummary?.average_relative_return_pct ??
                            null,
                        )}
                      </td>

                      <td className="px-2 py-4 text-sm text-text-primary">
                        {formatPercentage(
                          comparisonSummary?.average_relative_return_pct ??
                            null,
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function ComparisonPanel({
  title,
  run,
  report,
  provenance,
  provenanceUnavailable = false,
}: {
  title: string;
  run: BacktestRunResponse | null;
  report: BacktestPerformanceReport;
  provenance: BacktestProvenance | null;
  provenanceUnavailable?: boolean;
}) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle p-5">
      <div className="flex flex-col gap-5">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            {title}
          </p>

          <p className="mt-2 break-all text-xs text-text-muted">
            {report.backtest_id}
          </p>
        </div>

        {run && (
          <div className="flex flex-wrap items-center gap-2">
            {run.valid ? (
              <Badge variant="positive">Valid run</Badge>
            ) : (
              <Badge variant="warning">Run contains rejections</Badge>
            )}

            <span className="text-xs text-text-muted">
              Completed {formatTimestamp(run.completed_at)}
            </span>
          </div>
        )}

        <div className="grid gap-5 sm:grid-cols-2">
          <ComparisonMetric
            label="Evaluations"
            value={String(report.total_evaluations)}
          />

          <ComparisonMetric
            label="Directional accuracy"
            value={formatPercentage(report.directional_accuracy)}
          />

          <ComparisonMetric
            label="Average return"
            value={formatPercentage(report.average_forward_return_pct)}
          />

          <ComparisonMetric
            label="Relative return"
            value={formatPercentage(report.average_relative_return_pct)}
          />
        </div>

        <div className="border-t border-border pt-5">
          <div className="flex flex-wrap items-center gap-3">
            <QualityBadge state={report.quality_state} />

            <span className="text-sm text-text-secondary">
              {report.quality_evaluation_count} quality evaluations
            </span>
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <p className="text-sm font-semibold text-text-primary">
            Provenance
          </p>

          {provenance ? (
            <div className="mt-4 flex flex-col gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <ComparisonMetric
                  label="Ruleset"
                  value={provenance.ruleset_version}
                />

                <ComparisonMetric
                  label="Evidence references"
                  value={String(provenance.evidence.length)}
                />

                <ComparisonMetric
                  label="Input records"
                  value={String(provenance.input_ids.length)}
                />

                <ComparisonMetric
                  label="Stage"
                  value={formatStage(provenance.stage)}
                />
              </div>

              <ComparisonProvenanceList
                title="Assumptions"
                items={provenance.assumptions}
                emptyMessage="No assumptions recorded."
              />

              <ComparisonProvenanceList
                title="Invalidation conditions"
                items={provenance.invalidation_conditions}
                emptyMessage="No invalidation conditions recorded."
              />
            </div>
          ) : provenanceUnavailable ? (
            <p className="mt-3 text-sm leading-6 text-text-secondary">
              No persisted provenance record is available for this run.
            </p>
          ) : (
            <p className="mt-3 text-sm leading-6 text-text-secondary">
              Provenance is unavailable for comparison.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function ComparisonMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <p className="mt-1 break-words text-sm font-semibold text-text-primary">
        {value}
      </p>
    </div>
  );
}

function ComparisonProvenanceList({
  title,
  items,
  emptyMessage,
}: {
  title: string;
  items: string[];
  emptyMessage: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {title}
      </p>

      {items.length > 0 ? (
        <div className="mt-2 flex flex-col gap-2">
          {items.map((item) => (
            <div
              key={item}
              className="rounded-md border border-border bg-surface-subtle px-3 py-2 text-sm leading-6 text-text-secondary"
            >
              {item}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm leading-6 text-text-secondary">
          {emptyMessage}
        </p>
      )}
    </div>
  );
}

function ProvenanceCard({
  provenance,
  isLoading,
  unavailable,
  errorMessage,
}: {
  provenance: BacktestProvenance | null;
  isLoading: boolean;
  unavailable: boolean;
  errorMessage: string | null;
}) {
  if (isLoading) {
    return (
      <Card
        title="Provenance"
        description="Retrieving the evidence and ruleset metadata associated with this backtest."
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
    );
  }

  if (errorMessage) {
    return (
      <Card
        title="Provenance unavailable"
        description="The backtest report is available, but its persisted provenance could not be retrieved."
      >
        <p className="text-sm leading-6 text-text-secondary">
          {errorMessage}
        </p>
      </Card>
    );
  }

  if (unavailable || provenance === null) {
    return (
      <Card
        title="Provenance not available"
        description="This backtest has no persisted provenance record."
      >
        <p className="text-sm leading-6 text-text-secondary">
          The performance report can still be reviewed, but source evidence,
          assumptions, and invalidation conditions were not persisted for this
          run.
        </p>
      </Card>
    );
  }

  return (
    <Card
      title="Provenance"
      description="Traceability metadata recorded for the displayed backtest execution."
    >
      <div className="flex flex-col gap-7">
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
          <ProvenanceMetric
            label="Stage"
            value={formatStage(provenance.stage)}
          />

          <ProvenanceMetric
            label="Ruleset"
            value={provenance.ruleset_version}
          />

          <ProvenanceMetric
            label="Recorded"
            value={formatTimestamp(provenance.created_at)}
          />

          <ProvenanceMetric
            label="Input records"
            value={String(provenance.input_ids.length)}
          />
        </div>

        <div className="border-t border-border pt-6">
          <div className="flex flex-col gap-4">
            <div>
              <p className="text-sm font-semibold text-text-primary">
                Source evidence
              </p>

              <p className="mt-1 text-sm leading-6 text-text-secondary">
                Evidence references retained with this analysis result.
              </p>
            </div>

            {provenance.evidence.length > 0 ? (
              <div className="flex flex-col gap-3">
                {provenance.evidence.map((evidence) => (
                  <div
                    key={`${evidence.article_id}-${evidence.retrieved_at}`}
                    className="rounded-md border border-border bg-surface-subtle p-4"
                  >
                    <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-text-primary">
                          {evidence.source_name}
                        </p>

                        <p className="mt-1 break-all text-xs text-text-muted">
                          Article ID: {evidence.article_id}
                        </p>
                      </div>

                      {evidence.published_at && (
                        <span className="text-xs text-text-muted">
                          Published {formatTimestamp(evidence.published_at)}
                        </span>
                      )}
                    </div>

                    <p className="mt-3 text-sm leading-6 text-text-secondary">
                      {evidence.relevance_note}
                    </p>

                    <div className="mt-3">
                      <a
                        href={evidence.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="break-all text-sm font-medium text-brand underline decoration-brand/30 underline-offset-4 hover:decoration-brand"
                      >
                        {evidence.source_url}
                      </a>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-muted">
                      <span>
                        Discovered {formatTimestamp(evidence.discovered_at)}
                      </span>

                      <span>
                        Retrieved {formatTimestamp(evidence.retrieved_at)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-text-secondary">
                No source evidence was recorded for this result.
              </p>
            )}
          </div>
        </div>

        <div className="grid gap-6 border-t border-border pt-6 xl:grid-cols-2">
          <ProvenanceList
            title="Assumptions"
            items={provenance.assumptions}
            emptyMessage="No assumptions were recorded."
          />

          <ProvenanceList
            title="Invalidation conditions"
            items={provenance.invalidation_conditions}
            emptyMessage="No invalidation conditions were recorded."
          />
        </div>

        <div className="border-t border-border pt-6">
          <p className="text-sm font-semibold text-text-primary">
            Input record IDs
          </p>

          {provenance.input_ids.length > 0 ? (
            <div className="mt-3 max-h-44 overflow-y-auto rounded-md border border-border bg-surface-subtle p-3">
              <div className="flex flex-col gap-2">
                {provenance.input_ids.map((inputId) => (
                  <code
                    key={inputId}
                    className="break-all text-xs text-text-secondary"
                  >
                    {inputId}
                  </code>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              No input record IDs were recorded.
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}

function ProvenanceMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold capitalize text-text-primary">
        {value}
      </p>
    </div>
  );
}

function ProvenanceList({
  title,
  items,
  emptyMessage,
}: {
  title: string;
  items: string[];
  emptyMessage: string;
}) {
  return (
    <div>
      <p className="text-sm font-semibold text-text-primary">{title}</p>

      {items.length > 0 ? (
        <div className="mt-3 flex flex-col gap-2">
          {items.map((item) => (
            <div
              key={item}
              className="rounded-md border border-border bg-surface-subtle px-3 py-2 text-sm leading-6 text-text-secondary"
            >
              {item}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm leading-6 text-text-secondary">
          {emptyMessage}
        </p>
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
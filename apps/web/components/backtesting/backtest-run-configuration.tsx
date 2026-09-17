import type { ReactNode } from "react";

import type { BacktestRunResponse } from "../../lib/backtest-api";
import { Card } from "../ui/card";

type BacktestPeriod = NonNullable<
  BacktestRunResponse["configuration"]
>["training_periods"][number];

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

function formatPeriod(period: BacktestPeriod) {
  return `${formatTimestamp(period.start_at)} → ${formatTimestamp(period.end_at)}`;
}

function PeriodList({
  periods,
  emptyMessage,
}: {
  periods: BacktestPeriod[];
  emptyMessage: string;
}) {
  if (periods.length === 0) {
    return (
      <p className="text-sm leading-6 text-text-secondary">{emptyMessage}</p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {periods.map((period, index) => (
        <div
          key={`${period.start_at}-${period.end_at}-${index}`}
          className="rounded-md border border-border bg-surface-subtle px-3 py-2.5"
        >
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Period {index + 1}
          </p>

          <p className="mt-1 text-sm font-medium leading-6 text-text-primary">
            {formatPeriod(period)}
          </p>
        </div>
      ))}
    </div>
  );
}

function ConfigurationMetric({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <div className="mt-2">{children}</div>
    </div>
  );
}

export function BacktestRunConfigurationCard({
  run,
}: {
  run: BacktestRunResponse;
}) {
  const configuration = run.configuration;

  if (configuration === null) {
    return (
      <Card
        title="Run configuration"
        description="Persisted historical inputs associated with the selected backtest execution."
      >
        <div className="rounded-md border border-border bg-surface-subtle p-5">
          <p className="text-sm font-medium text-text-primary">
            Configuration unavailable
          </p>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-text-secondary">
            This run was persisted before run configuration snapshots were
            available, so MarketThread cannot reconstruct the original
            training, evaluation, or benchmark settings from the stored
            result.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card
      title="Run configuration"
      description="Persisted historical inputs associated with the selected backtest execution."
    >
      <div className="grid gap-6 xl:grid-cols-3">
        <ConfigurationMetric label="Training periods">
          <PeriodList
            periods={configuration.training_periods}
            emptyMessage="No training periods were persisted."
          />
        </ConfigurationMetric>

        <ConfigurationMetric label="Evaluation periods">
          <PeriodList
            periods={configuration.evaluation_periods}
            emptyMessage="No evaluation periods were persisted."
          />
        </ConfigurationMetric>

        <ConfigurationMetric label="Benchmark instrument">
          {configuration.benchmark_instrument_id ? (
            <code className="block break-all rounded-md border border-border bg-surface-subtle px-3 py-2.5 text-xs leading-5 text-text-secondary">
              {configuration.benchmark_instrument_id}
            </code>
          ) : (
            <div className="rounded-md border border-border bg-surface-subtle px-3 py-2.5">
              <p className="text-sm leading-6 text-text-secondary">
                No benchmark instrument configured.
              </p>
            </div>
          )}
        </ConfigurationMetric>
      </div>
    </Card>
  );
}

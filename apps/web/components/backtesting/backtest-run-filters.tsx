"use client";

import { Button } from "../ui/button";

export type BacktestRunStatusFilter = "all" | "valid" | "invalid";

type BacktestRunFiltersProps = {
  status: BacktestRunStatusFilter;
  completedAfter: string;
  completedBefore: string;
  isLoading: boolean;
  errorMessage: string | null;
  onStatusChange: (value: BacktestRunStatusFilter) => void;
  onCompletedAfterChange: (value: string) => void;
  onCompletedBeforeChange: (value: string) => void;
  onApply: () => void;
  onReset: () => void;
};

export function BacktestRunFilters({
  status,
  completedAfter,
  completedBefore,
  isLoading,
  errorMessage,
  onStatusChange,
  onCompletedAfterChange,
  onCompletedBeforeChange,
  onApply,
  onReset,
}: BacktestRunFiltersProps) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle p-4">
      <div className="flex flex-col gap-5">
        <div>
          <p className="text-sm font-semibold text-text-primary">
            Filter run history
          </p>

          <p className="mt-1 text-sm leading-6 text-text-secondary">
            Filters are applied on the server against persisted backtest run
            metadata. Completion dates are inclusive.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-text-primary">
              Run status
            </span>

            <select
              value={status}
              onChange={(event) =>
                onStatusChange(
                  event.target.value as BacktestRunStatusFilter,
                )
              }
              disabled={isLoading}
              className="w-full rounded-md border border-border bg-background px-3 py-2.5 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="all">All runs</option>
              <option value="valid">Valid runs</option>
              <option value="invalid">Runs with rejections</option>
            </select>
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-text-primary">
              Completed from
            </span>

            <input
              type="date"
              value={completedAfter}
              onChange={(event) => onCompletedAfterChange(event.target.value)}
              disabled={isLoading}
              className="w-full rounded-md border border-border bg-background px-3 py-2.5 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60"
            />
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-text-primary">
              Completed through
            </span>

            <input
              type="date"
              value={completedBefore}
              onChange={(event) => onCompletedBeforeChange(event.target.value)}
              disabled={isLoading}
              className="w-full rounded-md border border-border bg-background px-3 py-2.5 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60"
            />
          </label>
        </div>

        {errorMessage && (
          <div
            role="alert"
            className="rounded-md border border-border bg-warning-soft px-3 py-2.5 text-sm leading-6 text-warning"
          >
            {errorMessage}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
          <Button onClick={onApply} disabled={isLoading}>
            {isLoading ? "Applying filters" : "Apply filters"}
          </Button>

          <Button
            variant="secondary"
            onClick={onReset}
            disabled={isLoading}
          >
            Reset
          </Button>
        </div>
      </div>
    </div>
  );
}

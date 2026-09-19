"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createPortfolioCashFlow,
  fetchPortfolioCashFlows,
  PortfolioCashFlowApiError,
  type PortfolioCashFlowEventType,
  type PortfolioCashFlowResponse,
} from "../../lib/portfolio-cash-flow-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

type PortfolioCashFlowPanelProps = {
  portfolioId: string;
};

type LookbackOption = {
  value: string;
  label: string;
  days: number | null;
};

const LOOKBACK_OPTIONS: LookbackOption[] = [
  {
    value: "all",
    label: "All history",
    days: null,
  },
  {
    value: "30",
    label: "30 days",
    days: 30,
  },
  {
    value: "90",
    label: "90 days",
    days: 90,
  },
  {
    value: "365",
    label: "1 year",
    days: 365,
  },
  {
    value: "730",
    label: "2 years",
    days: 730,
  },
];

const CASH_FLOW_LIMIT = 500;

function getErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (error instanceof PortfolioCashFlowApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
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

function formatAmount(
  value: string,
  currency: string,
): string {
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

function getEffectiveAtInputValue(): string {
  const date = new Date();

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");

  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function toIsoTimestamp(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    throw new Error("Enter a valid effective date and time.");
  }

  return date.toISOString();
}

function getLookbackStart(
  lookbackDays: number | null,
): string | undefined {
  if (lookbackDays === null) {
    return undefined;
  }

  const start = new Date(
    Date.now() - lookbackDays * 24 * 60 * 60 * 1000,
  );

  return start.toISOString();
}

function getCurrencyCount(
  cashFlows: PortfolioCashFlowResponse[],
): number {
  return new Set(
    cashFlows.map((cashFlow) => cashFlow.currency),
  ).size;
}

function getEventCounts(
  cashFlows: PortfolioCashFlowResponse[],
): {
  deposits: number;
  withdrawals: number;
} {
  let deposits = 0;
  let withdrawals = 0;

  for (const cashFlow of cashFlows) {
    if (cashFlow.event_type === "deposit") {
      deposits += 1;
    } else {
      withdrawals += 1;
    }
  }

  return {
    deposits,
    withdrawals,
  };
}

export function PortfolioCashFlowPanel({
  portfolioId,
}: PortfolioCashFlowPanelProps) {
  const [cashFlows, setCashFlows] = useState<
    PortfolioCashFlowResponse[]
  >([]);

  const [lookbackKey, setLookbackKey] =
    useState("all");

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<
    string | null
  >(null);

  const [eventType, setEventType] =
    useState<PortfolioCashFlowEventType>("deposit");
  const [currency, setCurrency] = useState("USD");
  const [amount, setAmount] = useState("");
  const [effectiveAt, setEffectiveAt] =
    useState(getEffectiveAtInputValue());

  const [isCreating, setIsCreating] = useState(false);
  const [createErrorMessage, setCreateErrorMessage] =
    useState<string | null>(null);

  const lookbackDays = useMemo(
    () =>
      LOOKBACK_OPTIONS.find(
        (option) => option.value === lookbackKey,
      )?.days ?? null,
    [lookbackKey],
  );

  const loadCashFlows = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextCashFlows =
        await fetchPortfolioCashFlows(
          portfolioId,
          {
            startAt: getLookbackStart(lookbackDays),
            endAt:
              lookbackDays === null
                ? undefined
                : new Date().toISOString(),
            limit: CASH_FLOW_LIMIT,
          },
        );

      setCashFlows(nextCashFlows);
    } catch (error) {
      setCashFlows([]);
      setErrorMessage(
        getErrorMessage(
          error,
          "The portfolio cash-flow history could not be loaded.",
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, [lookbackDays, portfolioId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCashFlows();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadCashFlows]);

  const eventCounts = useMemo(
    () => getEventCounts(cashFlows),
    [cashFlows],
  );

  const currencyCount = useMemo(
    () => getCurrencyCount(cashFlows),
    [cashFlows],
  );

  const handleCreateCashFlow = async () => {
    const normalizedCurrency =
      currency.trim().toUpperCase();
    const normalizedAmount = amount.trim();

    setCreateErrorMessage(null);

    if (!/^[A-Z]{3}$/.test(normalizedCurrency)) {
      setCreateErrorMessage(
        "Enter a three-letter currency code.",
      );
      return;
    }

    if (!normalizedAmount) {
      setCreateErrorMessage(
        "Enter a positive cash-flow amount.",
      );
      return;
    }

    const numericAmount = Number(normalizedAmount);

    if (
      !Number.isFinite(numericAmount) ||
      numericAmount <= 0
    ) {
      setCreateErrorMessage(
        "Enter a positive cash-flow amount.",
      );
      return;
    }

    let normalizedEffectiveAt: string;

    try {
      normalizedEffectiveAt =
        toIsoTimestamp(effectiveAt);
    } catch (error) {
      setCreateErrorMessage(
        getErrorMessage(
          error,
          "Enter a valid effective date and time.",
        ),
      );
      return;
    }

    setIsCreating(true);

    try {
      await createPortfolioCashFlow(
        portfolioId,
        {
          event_type: eventType,
          currency: normalizedCurrency,
          amount: normalizedAmount,
          effective_at: normalizedEffectiveAt,
        },
      );

      setCurrency(normalizedCurrency);
      setAmount("");
      setEffectiveAt(getEffectiveAtInputValue());

      await loadCashFlows();
    } catch (error) {
      setCreateErrorMessage(
        getErrorMessage(
          error,
          "The cash flow could not be recorded.",
        ),
      );
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Card
      title="External cash-flow history"
      description="Record and review external deposits and withdrawals. These events are persisted separately and are not yet incorporated into portfolio performance or risk calculations."
    >
      <div className="flex flex-col gap-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(300px,1fr)_2fr]">
          <div className="rounded-md border border-border bg-surface-subtle p-5">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                Record external cash flow
              </p>

              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Use a deposit for money added to the portfolio
                and a withdrawal for money removed from it.
              </p>
            </div>

            <div className="mt-5 flex flex-col gap-4">
              <div>
                <label
                  htmlFor="portfolio-cash-flow-event-type"
                  className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted"
                >
                  Event type
                </label>

                <select
                  id="portfolio-cash-flow-event-type"
                  value={eventType}
                  onChange={(event) =>
                    setEventType(
                      event.target
                        .value as PortfolioCashFlowEventType,
                    )
                  }
                  disabled={isCreating}
                  className="mt-2 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <option value="deposit">
                    Deposit
                  </option>
                  <option value="withdrawal">
                    Withdrawal
                  </option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="portfolio-cash-flow-currency"
                  className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted"
                >
                  Currency
                </label>

                <input
                  id="portfolio-cash-flow-currency"
                  value={currency}
                  onChange={(event) =>
                    setCurrency(
                      event.target.value
                        .replace(/[^a-zA-Z]/g, "")
                        .slice(0, 3)
                        .toUpperCase(),
                    )
                  }
                  placeholder="USD"
                  maxLength={3}
                  disabled={isCreating}
                  className="mt-2 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm font-mono uppercase text-text-primary outline-none transition placeholder:text-text-muted focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60"
                />
              </div>

              <div>
                <label
                  htmlFor="portfolio-cash-flow-amount"
                  className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted"
                >
                  Amount
                </label>

                <input
                  id="portfolio-cash-flow-amount"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.00000001"
                  value={amount}
                  onChange={(event) =>
                    setAmount(event.target.value)
                  }
                  placeholder="1000"
                  disabled={isCreating}
                  className="mt-2 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm font-mono text-text-primary outline-none transition placeholder:text-text-muted focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60"
                />
              </div>

              <div>
                <label
                  htmlFor="portfolio-cash-flow-effective-at"
                  className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted"
                >
                  Effective at
                </label>

                <input
                  id="portfolio-cash-flow-effective-at"
                  type="datetime-local"
                  value={effectiveAt}
                  onChange={(event) =>
                    setEffectiveAt(event.target.value)
                  }
                  disabled={isCreating}
                  className="mt-2 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-60"
                />
              </div>

              {createErrorMessage && (
                <p
                  className="text-sm leading-6 text-negative"
                  role="alert"
                >
                  {createErrorMessage}
                </p>
              )}

              <div>
                <Button
                  onClick={() =>
                    void handleCreateCashFlow()
                  }
                  disabled={isCreating}
                >
                  {isCreating
                    ? "Recording cash flow"
                    : "Record cash flow"}
                </Button>
              </div>
            </div>
          </div>

          <div className="rounded-md border border-border bg-surface-subtle p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <label
                  htmlFor="portfolio-cash-flow-lookback"
                  className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted"
                >
                  History window
                </label>

                <select
                  id="portfolio-cash-flow-lookback"
                  value={lookbackKey}
                  onChange={(event) =>
                    setLookbackKey(event.target.value)
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
                onClick={() => void loadCashFlows()}
                disabled={isLoading}
              >
                {isLoading ? "Refreshing" : "Refresh history"}
              </Button>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              <HistoryMetric
                label="Events"
                value={cashFlows.length.toLocaleString()}
                description="Persisted external cash-flow records in the selected window."
              />

              <HistoryMetric
                label="Deposits"
                value={eventCounts.deposits.toLocaleString()}
                description="External additions recorded in the selected window."
              />

              <HistoryMetric
                label="Withdrawals"
                value={eventCounts.withdrawals.toLocaleString()}
                description="External removals recorded in the selected window."
              />
            </div>

            <div className="mt-4 rounded-md border border-border bg-surface px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-text-secondary">
                  Currencies represented
                </p>

                <p className="font-mono text-sm font-semibold text-text-primary">
                  {currencyCount.toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                Append-only ledger
              </p>

              <p className="mt-1 text-sm leading-6 text-text-secondary">
                Events are ordered by their effective timestamp.
                Sequence IDs preserve the original append order.
              </p>
            </div>

            <Badge variant="info">
              Up to {CASH_FLOW_LIMIT} events
            </Badge>
          </div>

          {errorMessage ? (
            <div className="mt-5 rounded-md border border-border bg-surface-subtle px-5 py-5">
              <p
                className="text-sm leading-6 text-text-secondary"
                role="alert"
              >
                {errorMessage}
              </p>

              <div className="mt-4">
                <Button
                  variant="ghost"
                  onClick={() => void loadCashFlows()}
                >
                  Try again
                </Button>
              </div>
            </div>
          ) : isLoading ? (
            <div className="mt-5 flex flex-col gap-3">
              {[1, 2, 3, 4].map((item) => (
                <div
                  key={item}
                  className="h-16 animate-pulse rounded-md bg-surface-muted"
                />
              ))}
            </div>
          ) : cashFlows.length === 0 ? (
            <div className="mt-5 rounded-md border border-border bg-surface-subtle px-5 py-10 text-center">
              <p className="text-sm font-medium text-text-primary">
                No external cash flows recorded.
              </p>

              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Record a deposit or withdrawal above to establish
                the portfolio&apos;s external cash-flow history.
              </p>
            </div>
          ) : (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[900px] border-separate border-spacing-0">
                <thead>
                  <tr className="text-left">
                    <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                      Effective
                    </th>

                    <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                      Type
                    </th>

                    <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                      Amount
                    </th>

                    <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                      Currency
                    </th>

                    <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                      Append sequence
                    </th>

                    <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                      Recorded
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {cashFlows.map((cashFlow) => {
                    const isDeposit =
                      cashFlow.event_type === "deposit";

                    return (
                      <tr key={cashFlow.cash_flow_id}>
                        <td className="border-b border-border px-3 py-4">
                          <p className="text-sm text-text-primary">
                            {formatTimestamp(
                              cashFlow.effective_at,
                            )}
                          </p>
                        </td>

                        <td className="border-b border-border px-3 py-4">
                          <Badge
                            variant={
                              isDeposit
                                ? "positive"
                                : "warning"
                            }
                          >
                            {isDeposit
                              ? "Deposit"
                              : "Withdrawal"}
                          </Badge>
                        </td>

                        <td className="border-b border-border px-3 py-4 text-right font-mono text-sm font-semibold text-text-primary">
                          {formatAmount(
                            cashFlow.amount,
                            cashFlow.currency,
                          )}
                        </td>

                        <td className="border-b border-border px-3 py-4">
                          <span className="font-mono text-sm text-text-secondary">
                            {cashFlow.currency}
                          </span>
                        </td>

                        <td className="border-b border-border px-3 py-4 text-right font-mono text-sm text-text-secondary">
                          #{cashFlow.sequence_id.toLocaleString()}
                        </td>

                        <td className="border-b border-border px-3 py-4 text-sm text-text-secondary">
                          {formatTimestamp(
                            cashFlow.recorded_at,
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function HistoryMetric({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <div className="rounded-md border border-border bg-surface px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <p className="mt-2 text-lg font-semibold text-text-primary">
        {value}
      </p>

      <p className="mt-2 text-xs leading-5 text-text-secondary">
        {description}
      </p>
    </div>
  );
}

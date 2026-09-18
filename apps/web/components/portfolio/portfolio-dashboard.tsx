"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "../auth/auth-provider";
import { PortfolioExposurePanel } from "./portfolio-exposure-panel";
import { PortfolioPerformancePanel } from "./portfolio-performance-panel";
import { PortfolioPositionForm } from "./portfolio-position-form";
import { PortfolioValuationPanel } from "./portfolio-valuation-panel";
import {
  createPortfolio,
  deletePortfolio,
  fetchPortfolio,
  fetchPortfolioExposure,
  fetchPortfolioPerformance,
  fetchPortfolioValuation,
  fetchPortfolios,
  PortfolioApiError,
  removePortfolioPosition,
  type Portfolio,
  type PortfolioDetail,
  type PortfolioExposureResponse,
  type PortfolioPerformanceResponse,
  type PortfolioPosition,
  type PortfolioValuationResponse,
} from "../../lib/portfolio-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof PortfolioApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
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

function formatQuantity(value: string) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 8,
  }).format(numericValue);
}

function formatPrice(value: string, currency: string) {
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

function calculateCostBasis(
  quantity: string,
  averageCost: string,
): number | null {
  const parsedQuantity = Number(quantity);
  const parsedAverageCost = Number(averageCost);

  if (
    !Number.isFinite(parsedQuantity) ||
    !Number.isFinite(parsedAverageCost)
  ) {
    return null;
  }

  return parsedQuantity * parsedAverageCost;
}

function getCostBasisGroups(
  positions: PortfolioPosition[],
): Map<string, number> {
  const groups = new Map<string, number>();

  for (const position of positions) {
    const costBasis = calculateCostBasis(
      position.quantity,
      position.average_cost,
    );

    if (costBasis === null) {
      continue;
    }

    groups.set(
      position.currency,
      (groups.get(position.currency) ?? 0) + costBasis,
    );
  }

  return groups;
}

function formatCostBasisSummary(
  positions: PortfolioPosition[],
) {
  const groups = getCostBasisGroups(positions);

  if (groups.size === 0) {
    return "—";
  }

  if (groups.size === 1) {
    const [currency, amount] = [...groups.entries()][0];

    return formatPrice(String(amount), currency);
  }

  return `${groups.size} currencies`;
}

export function PortfolioDashboard() {
  const router = useRouter();
  const { user, isLoading: isAuthLoading, isAuthenticated } =
    useAuth();

  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] =
    useState<string | null>(null);
  const [selectedPortfolio, setSelectedPortfolio] =
    useState<PortfolioDetail | null>(null);
  const [selectedValuation, setSelectedValuation] =
    useState<PortfolioValuationResponse | null>(null);
  const [selectedExposure, setSelectedExposure] =
    useState<PortfolioExposureResponse | null>(null);
  const [selectedPerformance, setSelectedPerformance] =
    useState<PortfolioPerformanceResponse | null>(null);

  const [performanceLookbackDays, setPerformanceLookbackDays] =
    useState(365);

  const [isLoading, setIsLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isValuationLoading, setIsValuationLoading] =
    useState(false);
  const [isExposureLoading, setIsExposureLoading] =
    useState(false);
  const [isPerformanceLoading, setIsPerformanceLoading] =
    useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(
    null,
  );
  const [detailErrorMessage, setDetailErrorMessage] = useState<
    string | null
  >(null);
  const [valuationErrorMessage, setValuationErrorMessage] =
    useState<string | null>(null);
  const [exposureErrorMessage, setExposureErrorMessage] =
    useState<string | null>(null);
  const [performanceErrorMessage, setPerformanceErrorMessage] =
    useState<string | null>(null);

  const [portfolioName, setPortfolioName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createErrorMessage, setCreateErrorMessage] = useState<
    string | null
  >(null);

  const [removingPositionId, setRemovingPositionId] = useState<
    string | null
  >(null);

  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteErrorMessage, setDeleteErrorMessage] = useState<
    string | null
  >(null);

  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      router.replace(
        `/login?next=${encodeURIComponent("/portfolio")}`,
      );
    }
  }, [isAuthLoading, isAuthenticated, router]);

  const loadPortfolios = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextPortfolios = await fetchPortfolios();

      setPortfolios(nextPortfolios);

      setSelectedPortfolioId((currentId) => {
        if (
          currentId &&
          nextPortfolios.some(
            (portfolio) => portfolio.portfolio_id === currentId,
          )
        ) {
          return currentId;
        }

        return nextPortfolios[0]?.portfolio_id ?? null;
      });
    } catch (error) {
      setPortfolios([]);
      setSelectedPortfolioId(null);
      setErrorMessage(
        getErrorMessage(
          error,
          "Your portfolios could not be loaded.",
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthLoading || !isAuthenticated) {
      return;
    }

    const timer = window.setTimeout(() => {
      void loadPortfolios();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [isAuthLoading, isAuthenticated, loadPortfolios]);

  const loadSelectedPortfolioValuation = useCallback(
    async (portfolioId: string) => {
      setIsValuationLoading(true);
      setValuationErrorMessage(null);

      try {
        const valuation = await fetchPortfolioValuation(
          portfolioId,
          900,
        );

        setSelectedValuation(valuation);
      } catch (error) {
        setSelectedValuation(null);
        setValuationErrorMessage(
          getErrorMessage(
            error,
            "The portfolio valuation could not be loaded.",
          ),
        );
      } finally {
        setIsValuationLoading(false);
      }
    },
    [],
  );

  const loadSelectedPortfolioExposure = useCallback(
    async (portfolioId: string) => {
      setIsExposureLoading(true);
      setExposureErrorMessage(null);

      try {
        const exposure = await fetchPortfolioExposure(
          portfolioId,
          900,
        );

        setSelectedExposure(exposure);
      } catch (error) {
        setSelectedExposure(null);
        setExposureErrorMessage(
          getErrorMessage(
            error,
            "The portfolio exposure could not be loaded.",
          ),
        );
      } finally {
        setIsExposureLoading(false);
      }
    },
    [],
  );

  const loadSelectedPortfolioPerformance = useCallback(
    async (
      portfolioId: string,
      lookbackDays: number,
    ) => {
      setIsPerformanceLoading(true);
      setPerformanceErrorMessage(null);

      try {
        const performance = await fetchPortfolioPerformance(
          portfolioId,
          lookbackDays,
        );

        setSelectedPerformance(performance);
      } catch (error) {
        setSelectedPerformance(null);
        setPerformanceErrorMessage(
          getErrorMessage(
            error,
            "The historical portfolio performance could not be loaded.",
          ),
        );
      } finally {
        setIsPerformanceLoading(false);
      }
    },
    [],
  );

  const loadSelectedPortfolio = useCallback(
    async (portfolioId: string) => {
      setIsDetailLoading(true);
      setDetailErrorMessage(null);
      setSelectedValuation(null);
      setValuationErrorMessage(null);
      setSelectedExposure(null);
      setExposureErrorMessage(null);
      setSelectedPerformance(null);
      setPerformanceErrorMessage(null);

      try {
        const detail = await fetchPortfolio(portfolioId);

        setSelectedPortfolio(detail);
      } catch (error) {
        setSelectedPortfolio(null);
        setDetailErrorMessage(
          getErrorMessage(
            error,
            "The selected portfolio could not be loaded.",
          ),
        );
      } finally {
        setIsDetailLoading(false);
      }

      void loadSelectedPortfolioValuation(portfolioId);
      void loadSelectedPortfolioExposure(portfolioId);
    },
    [
      loadSelectedPortfolioExposure,
      loadSelectedPortfolioValuation,
    ],
  );

  useEffect(() => {
    if (!selectedPortfolioId) {
      return;
    }

    const timer = window.setTimeout(() => {
      void loadSelectedPortfolioPerformance(
        selectedPortfolioId,
        performanceLookbackDays,
      );
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [
    selectedPortfolioId,
    performanceLookbackDays,
    loadSelectedPortfolioPerformance,
  ]);

  useEffect(() => {
    if (!selectedPortfolioId) {
      return;
    }

    const timer = window.setTimeout(() => {
      void loadSelectedPortfolio(selectedPortfolioId);
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [selectedPortfolioId, loadSelectedPortfolio]);

  const selectedPortfolioSummary = useMemo(
    () =>
      portfolios.find(
        (portfolio) =>
          portfolio.portfolio_id === selectedPortfolioId,
      ) ?? null,
    [portfolios, selectedPortfolioId],
  );

  const portfolioMetrics = useMemo(() => {
    const positions = selectedPortfolio?.positions ?? [];

    return {
      positions: positions.length,
      activePositions: positions.filter(
        (position) => position.is_active,
      ).length,
      currencies: new Set(
        positions.map((position) => position.currency),
      ).size,
      costBasis: formatCostBasisSummary(positions),
    };
  }, [selectedPortfolio]);

  const handleCreatePortfolio = async () => {
    const name = portfolioName.trim();

    if (!name) {
      setCreateErrorMessage("Enter a name for the new portfolio.");
      return;
    }

    setIsCreating(true);
    setCreateErrorMessage(null);

    try {
      const created = await createPortfolio(name);

      setPortfolioName("");
      await loadPortfolios();
      setSelectedPortfolioId(created.portfolio_id);
    } catch (error) {
      setCreateErrorMessage(
        getErrorMessage(
          error,
          "The portfolio could not be created.",
        ),
      );
    } finally {
      setIsCreating(false);
    }
  };

  const handlePositionSaved = async () => {
    if (!selectedPortfolioId) {
      return;
    }

    await Promise.all([
      loadPortfolios(),
      loadSelectedPortfolio(selectedPortfolioId),
      loadSelectedPortfolioPerformance(
        selectedPortfolioId,
        performanceLookbackDays,
      ),
    ]);
  };

  const handleRemovePosition = async (
    position: PortfolioPosition,
  ) => {
    if (!selectedPortfolioId) {
      return;
    }

    setRemovingPositionId(position.position_id);
    setDetailErrorMessage(null);

    try {
      await removePortfolioPosition(
        selectedPortfolioId,
        position.position_id,
      );

      await Promise.all([
        loadPortfolios(),
        loadSelectedPortfolio(selectedPortfolioId),
        loadSelectedPortfolioPerformance(
          selectedPortfolioId,
          performanceLookbackDays,
        ),
      ]);
    } catch (error) {
      setDetailErrorMessage(
        getErrorMessage(
          error,
          "The portfolio position could not be removed.",
        ),
      );
    } finally {
      setRemovingPositionId(null);
    }
  };

  const handleDeletePortfolio = async () => {
    if (!selectedPortfolioId || !selectedPortfolio) {
      return;
    }

    const confirmed = window.confirm(
      `Delete the "${selectedPortfolio.name}" portfolio? This will remove its persisted current positions.`,
    );

    if (!confirmed) {
      return;
    }

    setIsDeleting(true);
    setDeleteErrorMessage(null);

    try {
      await deletePortfolio(selectedPortfolioId);

      setSelectedPortfolio(null);
      setSelectedValuation(null);
      setSelectedExposure(null);
      setSelectedPerformance(null);
      setSelectedPortfolioId(null);

      await loadPortfolios();
    } catch (error) {
      setDeleteErrorMessage(
        getErrorMessage(
          error,
          "The portfolio could not be deleted.",
        ),
      );
    } finally {
      setIsDeleting(false);
    }
  };

  if (isAuthLoading) {
    return (
      <div className="flex min-h-80 items-center justify-center">
        <p className="text-sm text-text-secondary">
          Restoring your MarketThread session…
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-80 items-center justify-center">
        <p className="text-sm text-text-secondary">
          Redirecting to sign in…
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Portfolio</Badge>
          <Badge variant="positive">Authenticated</Badge>
        </div>

        <div>
          <p className="text-sm font-medium text-brand">
            MarketThread
          </p>

          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            Portfolio intelligence workspace
          </h1>

          <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
            Maintain persisted holdings and inspect server-backed
            valuation, historical performance, and exposure with
            explicit data-quality and currency boundaries.
          </p>

          {user && (
            <p className="mt-2 text-sm text-text-muted">
              Signed in as {user.email}
            </p>
          )}
        </div>
      </header>

      {errorMessage ? (
        <Card
          title="Portfolios unavailable"
          description="MarketThread could not retrieve your persisted portfolios."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button onClick={() => void loadPortfolios()}>
                Try again
              </Button>
            </div>
          </div>
        </Card>
      ) : (
        <>
          <section className="grid gap-5 lg:grid-cols-[minmax(280px,1fr)_2fr]">
            <Card
              title="Create portfolio"
              description="Create a named portfolio for your current holdings."
            >
              <div className="flex flex-col gap-4">
                <Input
                  label="Portfolio name"
                  value={portfolioName}
                  onChange={(event) =>
                    setPortfolioName(event.target.value)
                  }
                  placeholder="e.g. Long-term holdings"
                  maxLength={100}
                  disabled={isCreating}
                  error={createErrorMessage ?? undefined}
                />

                <div>
                  <Button
                    onClick={() => void handleCreatePortfolio()}
                    disabled={isCreating}
                  >
                    {isCreating
                      ? "Creating portfolio"
                      : "Create portfolio"}
                  </Button>
                </div>
              </div>
            </Card>

            <Card
              title="Your portfolios"
              description="Select a persisted portfolio to review and update its current holdings."
            >
              {isLoading ? (
                <div className="flex flex-col gap-3">
                  {[1, 2, 3].map((item) => (
                    <div
                      key={item}
                      className="h-16 animate-pulse rounded-md bg-surface-muted"
                    />
                  ))}
                </div>
              ) : portfolios.length === 0 ? (
                <div className="rounded-md border border-border bg-surface-subtle px-5 py-9 text-center">
                  <p className="text-sm font-medium text-text-primary">
                    No portfolios yet.
                  </p>

                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    Create a portfolio above to begin recording current
                    positions.
                  </p>
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {portfolios.map((portfolio) => {
                    const isSelected =
                      portfolio.portfolio_id ===
                      selectedPortfolioId;

                    return (
                      <button
                        key={portfolio.portfolio_id}
                        type="button"
                        onClick={() =>
                          setSelectedPortfolioId(
                            portfolio.portfolio_id,
                          )
                        }
                        className={[
                          "rounded-md border p-4 text-left transition-colors",
                          isSelected
                            ? "border-brand bg-brand/5"
                            : "border-border bg-surface hover:bg-surface-muted",
                        ].join(" ")}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-text-primary">
                              {portfolio.name}
                            </p>

                            <p className="mt-1 text-xs text-text-muted">
                              Updated{" "}
                              {formatTimestamp(
                                portfolio.updated_at,
                              )}
                            </p>
                          </div>

                          <Badge
                            variant={
                              isSelected ? "info" : "neutral"
                            }
                          >
                            {portfolio.position_count}
                          </Badge>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </Card>
          </section>

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Metric
              label="Positions"
              value={String(portfolioMetrics.positions)}
              description="Persisted current positions in the selected portfolio."
            />

            <Metric
              label="Active instruments"
              value={String(portfolioMetrics.activePositions)}
              description="Positions whose canonical instruments remain active."
            />

            <Metric
              label="Currencies"
              value={String(portfolioMetrics.currencies)}
              description="Distinct currencies represented by current positions."
            />

            <Metric
              label="Cost basis"
              value={portfolioMetrics.costBasis}
              description="Derived from stored quantity and average cost."
            />
          </section>

          {!selectedPortfolioId ? (
            <Card
              title="Select a portfolio"
              description="Choose a portfolio above to manage its positions."
            >
              <div className="rounded-md border border-border bg-surface-subtle px-5 py-10 text-center">
                <p className="text-sm font-medium text-text-primary">
                  No portfolio selected
                </p>

                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  Create or select a portfolio to continue.
                </p>
              </div>
            </Card>
          ) : isDetailLoading ? (
            <Card
              title="Loading portfolio"
              description="Retrieving its persisted positions."
            >
              <div className="flex flex-col gap-3">
                {[1, 2, 3].map((item) => (
                  <div
                    key={item}
                    className="h-20 animate-pulse rounded-md bg-surface-muted"
                  />
                ))}
              </div>
            </Card>
          ) : detailErrorMessage ? (
            <Card
              title="Portfolio details unavailable"
              description="The selected portfolio could not be retrieved."
            >
              <div className="flex flex-col gap-4">
                <p
                  className="text-sm leading-6 text-text-secondary"
                  role="alert"
                >
                  {detailErrorMessage}
                </p>

                <div>
                  <Button
                    onClick={() =>
                      selectedPortfolioId &&
                      void loadSelectedPortfolio(
                        selectedPortfolioId,
                      )
                    }
                  >
                    Try again
                  </Button>
                </div>
              </div>
            </Card>
          ) : selectedPortfolio ? (
            <>
              <PortfolioValuationPanel
                valuation={selectedValuation}
                isLoading={isValuationLoading}
                errorMessage={valuationErrorMessage}
                onRefresh={() =>
                  void loadSelectedPortfolioValuation(
                    selectedPortfolio.portfolio_id,
                  )
                }
              />

              <PortfolioPerformancePanel
                performance={selectedPerformance}
                isLoading={isPerformanceLoading}
                errorMessage={performanceErrorMessage}
                lookbackDays={performanceLookbackDays}
                onLookbackDaysChange={setPerformanceLookbackDays}
                onRefresh={() =>
                  void loadSelectedPortfolioPerformance(
                    selectedPortfolio.portfolio_id,
                    performanceLookbackDays,
                  )
                }
              />

              <PortfolioExposurePanel
                exposure={selectedExposure}
                isLoading={isExposureLoading}
                errorMessage={exposureErrorMessage}
                onRefresh={() =>
                  void loadSelectedPortfolioExposure(
                    selectedPortfolio.portfolio_id,
                  )
                }
              />

              <PortfolioPositionForm
                portfolioId={selectedPortfolio.portfolio_id}
                onPositionSaved={handlePositionSaved}
              />

              <Card
                title={selectedPortfolio.name}
                description={`${selectedPortfolio.positions.length} current position${
                  selectedPortfolio.positions.length === 1
                    ? ""
                    : "s"
                }.`}
              >
                {selectedPortfolio.positions.length === 0 ? (
                  <div className="rounded-md border border-border bg-surface-subtle px-5 py-10 text-center">
                    <p className="text-sm font-medium text-text-primary">
                      This portfolio has no current positions.
                    </p>

                    <p className="mt-2 text-sm leading-6 text-text-secondary">
                      Resolve an active instrument above and save its
                      current quantity and average cost.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[920px] border-separate border-spacing-0">
                      <thead>
                        <tr className="text-left">
                          <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Instrument
                          </th>

                          <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Quantity
                          </th>

                          <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Average cost
                          </th>

                          <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Cost basis
                          </th>

                          <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Instrument state
                          </th>

                          <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Action
                          </th>
                        </tr>
                      </thead>

                      <tbody>
                        {selectedPortfolio.positions.map(
                          (position) => {
                            const costBasis =
                              calculateCostBasis(
                                position.quantity,
                                position.average_cost,
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
                                  {formatQuantity(
                                    position.quantity,
                                  )}
                                </td>

                                <td className="border-b border-border px-3 py-4 text-right text-sm text-text-secondary">
                                  {formatPrice(
                                    position.average_cost,
                                    position.currency,
                                  )}
                                </td>

                                <td className="border-b border-border px-3 py-4 text-right text-sm font-medium text-text-primary">
                                  {costBasis === null
                                    ? "—"
                                    : formatPrice(
                                        String(costBasis),
                                        position.currency,
                                      )}
                                </td>

                                <td className="border-b border-border px-3 py-4">
                                  <Badge
                                    variant={
                                      position.is_active
                                        ? "positive"
                                        : "warning"
                                    }
                                  >
                                    {position.is_active
                                      ? "Active"
                                      : "Inactive"}
                                  </Badge>
                                </td>

                                <td className="border-b border-border px-3 py-4 text-right">
                                  <Button
                                    variant="ghost"
                                    onClick={() =>
                                      void handleRemovePosition(
                                        position,
                                      )
                                    }
                                    disabled={
                                      removingPositionId ===
                                      position.position_id
                                    }
                                  >
                                    {removingPositionId ===
                                    position.position_id
                                      ? "Removing"
                                      : "Remove"}
                                  </Button>
                                </td>
                              </tr>
                            );
                          },
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>

              {deleteErrorMessage && (
                <p
                  className="text-sm leading-6 text-negative"
                  role="alert"
                >
                  {deleteErrorMessage}
                </p>
              )}

              <Card
                title="Portfolio readiness"
                description="Current capabilities and intentionally deferred calculations."
              >
                <div className="grid gap-4 md:grid-cols-3">
                  <ReadinessNote
                    title="Persisted holdings"
                    description="Current quantity and average cost are stored against canonical instruments."
                  />

                  <ReadinessNote
                    title="Server-backed valuation"
                    description="Market value and unrealized performance now use persisted positions plus explicit quote freshness."
                  />

                  <ReadinessNote
                    title="Exposure analysis"
                    description="Currency, asset-class, and position concentration are derived from quality-aware valuation data without creating a fabricated portfolio risk score."
                  />
                </div>
              </Card>

              <div className="flex flex-col gap-4 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                    Portfolio metadata
                  </p>

                  <p className="mt-1 text-sm text-text-secondary">
                    Created{" "}
                    {formatTimestamp(
                      selectedPortfolio.created_at,
                    )}
                  </p>
                </div>

                <Button
                  variant="danger"
                  onClick={() =>
                    void handleDeletePortfolio()
                  }
                  disabled={isDeleting}
                >
                  {isDeleting
                    ? "Deleting portfolio"
                    : "Delete portfolio"}
                </Button>
              </div>
            </>
          ) : null}

          {selectedPortfolioSummary && (
            <p className="text-xs leading-5 text-text-muted">
              Last portfolio summary update:{" "}
              {formatTimestamp(
                selectedPortfolioSummary.updated_at,
              )}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <Card>
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
          {label}
        </p>

        <p className="mt-2 text-2xl font-semibold tracking-tight text-text-primary">
          {value}
        </p>

        <p className="mt-2 text-xs leading-5 text-text-secondary">
          {description}
        </p>
      </div>
    </Card>
  );
}

function ReadinessNote({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle px-4 py-4">
      <p className="text-sm font-semibold text-text-primary">
        {title}
      </p>

      <p className="mt-2 text-sm leading-6 text-text-secondary">
        {description}
      </p>
    </div>
  );
}

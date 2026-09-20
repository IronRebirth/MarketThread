"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { AuthRequiredPrompt } from "../auth/auth-required-prompt";
import {
  fetchInstrument,
  MarketDataApiError,
  type Instrument,
} from "../../lib/market-data-api";
import {
  addWatchlistItem,
  createWatchlist,
  deleteWatchlist,
  fetchWatchlist,
  fetchWatchlists,
  removeWatchlistItem,
  WatchlistsApiError,
  type Watchlist,
  type WatchlistDetail,
  type WatchlistItem,
} from "../../lib/watchlists-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";

function getErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (error instanceof WatchlistsApiError) {
    return error.message;
  }

  if (error instanceof MarketDataApiError) {
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

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

export function WatchlistDashboard() {
  const { user, isLoading: isAuthLoading, isAuthenticated } =
    useAuth();

  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [selectedWatchlistId, setSelectedWatchlistId] =
    useState<string | null>(null);
  const [selectedWatchlist, setSelectedWatchlist] =
    useState<WatchlistDetail | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(
    null,
  );
  const [detailErrorMessage, setDetailErrorMessage] = useState<
    string | null
  >(null);

  const [watchlistName, setWatchlistName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createErrorMessage, setCreateErrorMessage] = useState<
    string | null
  >(null);

  const [ticker, setTicker] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [instrumentPreview, setInstrumentPreview] =
    useState<Instrument | null>(null);
  const [addErrorMessage, setAddErrorMessage] = useState<string | null>(
    null,
  );

  const [removingItemId, setRemovingItemId] = useState<string | null>(
    null,
  );
  const [deletingWatchlist, setDeletingWatchlist] = useState(false);
  const [deleteErrorMessage, setDeleteErrorMessage] = useState<
    string | null
  >(null);

  const loadWatchlists = useCallback(
    async (preferredWatchlistId?: string | null) => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const nextWatchlists = await fetchWatchlists();

        setWatchlists(nextWatchlists);

        const preferredExists =
          preferredWatchlistId !== null &&
          preferredWatchlistId !== undefined &&
          nextWatchlists.some(
            (watchlist) =>
              watchlist.watchlist_id === preferredWatchlistId,
          );

        const currentExists =
          selectedWatchlistId !== null &&
          nextWatchlists.some(
            (watchlist) =>
              watchlist.watchlist_id === selectedWatchlistId,
          );

        const nextSelectedId = preferredExists
          ? preferredWatchlistId
          : currentExists
            ? selectedWatchlistId
            : nextWatchlists[0]?.watchlist_id ?? null;

        setSelectedWatchlistId(nextSelectedId);
      } catch (error) {
        setWatchlists([]);
        setSelectedWatchlistId(null);

        setErrorMessage(
          getErrorMessage(
            error,
            "Your watchlists could not be loaded.",
          ),
        );
      } finally {
        setIsLoading(false);
      }
    },
    [selectedWatchlistId],
  );

  const loadSelectedWatchlist = useCallback(
    async (watchlistId: string) => {
      setIsDetailLoading(true);
      setDetailErrorMessage(null);

      try {
        const detail = await fetchWatchlist(watchlistId);

        setSelectedWatchlist(detail);
      } catch (error) {
        setSelectedWatchlist(null);

        setDetailErrorMessage(
          getErrorMessage(
            error,
            "The selected watchlist could not be loaded.",
          ),
        );
      } finally {
        setIsDetailLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (isAuthLoading || !isAuthenticated) {
      return;
    }

    let cancelled = false;

    const initializeWatchlists = async () => {
      try {
        const nextWatchlists = await fetchWatchlists();

        if (cancelled) {
          return;
        }

        setWatchlists(nextWatchlists);
        setSelectedWatchlistId(
          nextWatchlists[0]?.watchlist_id ?? null,
        );
        setErrorMessage(null);
      } catch (error) {
        if (cancelled) {
          return;
        }

        setWatchlists([]);
        setSelectedWatchlistId(null);

        setErrorMessage(
          getErrorMessage(
            error,
            "Your watchlists could not be loaded.",
          ),
        );
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void initializeWatchlists();

    return () => {
      cancelled = true;
    };
  }, [isAuthLoading, isAuthenticated]);

  useEffect(() => {
    if (!selectedWatchlistId) {
      return;
    }

    let cancelled = false;

    const loadDetail = async () => {
      setIsDetailLoading(true);
      setDetailErrorMessage(null);

      try {
        const detail = await fetchWatchlist(selectedWatchlistId);

        if (cancelled) {
          return;
        }

        setSelectedWatchlist(detail);
      } catch (error) {
        if (cancelled) {
          return;
        }

        setSelectedWatchlist(null);

        setDetailErrorMessage(
          getErrorMessage(
            error,
            "The selected watchlist could not be loaded.",
          ),
        );
      } finally {
        if (!cancelled) {
          setIsDetailLoading(false);
        }
      }
    };

    void loadDetail();

    return () => {
      cancelled = true;
    };
  }, [selectedWatchlistId]);

  const selectedListSummary = useMemo(
    () =>
      watchlists.find(
        (watchlist) =>
          watchlist.watchlist_id === selectedWatchlistId,
      ) ?? null,
    [selectedWatchlistId, watchlists],
  );

  const handleCreateWatchlist = async () => {
    const name = watchlistName.trim();

    if (!name) {
      setCreateErrorMessage("Enter a name for the new watchlist.");
      return;
    }

    setIsCreating(true);
    setCreateErrorMessage(null);

    try {
      const created = await createWatchlist(name);

      setWatchlistName("");

      await loadWatchlists(created.watchlist_id);
    } catch (error) {
      setCreateErrorMessage(
        getErrorMessage(
          error,
          "The watchlist could not be created.",
        ),
      );
    } finally {
      setIsCreating(false);
    }
  };

  const handleResolveInstrument = async () => {
    const normalizedTicker = ticker.trim().toUpperCase();

    if (!normalizedTicker) {
      setAddErrorMessage("Enter a ticker symbol.");
      setInstrumentPreview(null);
      return;
    }

    setAddErrorMessage(null);
    setInstrumentPreview(null);
    setIsAdding(true);

    try {
      const instrument = await fetchInstrument(normalizedTicker);

      if (!instrument.is_active) {
        setAddErrorMessage(
          "This instrument is currently inactive.",
        );
        return;
      }

      setInstrumentPreview(instrument);
    } catch (error) {
      setAddErrorMessage(
        getErrorMessage(
          error,
          "The instrument could not be resolved.",
        ),
      );
    } finally {
      setIsAdding(false);
    }
  };

  const handleAddInstrument = async () => {
    if (!selectedWatchlistId || !instrumentPreview) {
      return;
    }

    setIsAdding(true);
    setAddErrorMessage(null);

    try {
      await addWatchlistItem(
        selectedWatchlistId,
        instrumentPreview.id,
      );

      setTicker("");
      setInstrumentPreview(null);

      await Promise.all([
        loadWatchlists(selectedWatchlistId),
        loadSelectedWatchlist(selectedWatchlistId),
      ]);
    } catch (error) {
      setAddErrorMessage(
        getErrorMessage(
          error,
          "The instrument could not be added to the watchlist.",
        ),
      );
    } finally {
      setIsAdding(false);
    }
  };

  const handleRemoveItem = async (item: WatchlistItem) => {
    if (!selectedWatchlistId) {
      return;
    }

    setRemovingItemId(item.item_id);
    setDetailErrorMessage(null);

    try {
      await removeWatchlistItem(
        selectedWatchlistId,
        item.item_id,
      );

      await Promise.all([
        loadWatchlists(selectedWatchlistId),
        loadSelectedWatchlist(selectedWatchlistId),
      ]);
    } catch (error) {
      setDetailErrorMessage(
        getErrorMessage(
          error,
          "The instrument could not be removed.",
        ),
      );
    } finally {
      setRemovingItemId(null);
    }
  };

  const handleDeleteWatchlist = async () => {
    if (!selectedWatchlistId || !selectedWatchlist) {
      return;
    }

    const confirmed = window.confirm(
      `Delete the "${selectedWatchlist.name}" watchlist? This will remove its tracked instruments.`,
    );

    if (!confirmed) {
      return;
    }

    setDeletingWatchlist(true);
    setDeleteErrorMessage(null);

    try {
      await deleteWatchlist(selectedWatchlistId);

      setSelectedWatchlist(null);
      setSelectedWatchlistId(null);

      await loadWatchlists();
    } catch (error) {
      setDeleteErrorMessage(
        getErrorMessage(
          error,
          "The watchlist could not be deleted.",
        ),
      );
    } finally {
      setDeletingWatchlist(false);
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
      <div className="flex flex-col gap-8">
        <header className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">Watchlists</Badge>
          </div>
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Your watchlists
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Track the market instruments you want to monitor alongside
              MarketThread&apos;s research intelligence.
            </p>
          </div>
        </header>
        <AuthRequiredPrompt nextPath="/watchlists" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Watchlists</Badge>
          <Badge variant="positive">Authenticated</Badge>
        </div>

        <div>
          <p className="text-sm font-medium text-brand">
            MarketThread
          </p>

          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            Your watchlists
          </h1>

          <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
            Track the market instruments you want to monitor alongside
            MarketThread&apos;s research intelligence.
          </p>

          {user && (
            <p className="mt-2 text-sm text-text-muted">
              Signed in as {user.email}
            </p>
          )}
        </div>
      </header>

      {errorMessage && (
        <Card
          title="Watchlists unavailable"
          description="MarketThread could not retrieve your persisted watchlists."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button onClick={() => void loadWatchlists()}>
                Try again
              </Button>
            </div>
          </div>
        </Card>
      )}

      {!errorMessage && (
        <>
          <section className="grid gap-5 lg:grid-cols-[1fr_2fr]">
            <Card
              title="Create watchlist"
              description="Create a named workspace for instruments you want to monitor."
            >
              <div className="flex flex-col gap-4">
                <Input
                  label="Watchlist name"
                  value={watchlistName}
                  onChange={(event) =>
                    setWatchlistName(event.target.value)
                  }
                  placeholder="e.g. Core technology"
                  maxLength={100}
                  disabled={isCreating}
                  error={createErrorMessage ?? undefined}
                />

                <div>
                  <Button
                    onClick={() => void handleCreateWatchlist()}
                    disabled={isCreating}
                  >
                    {isCreating
                      ? "Creating watchlist"
                      : "Create watchlist"}
                  </Button>
                </div>
              </div>
            </Card>

            <Card
              title="Your watchlists"
              description="Select one of your persisted watchlists to manage its tracked instruments."
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
              ) : watchlists.length === 0 ? (
                <div className="rounded-md border border-border bg-surface-subtle px-5 py-8 text-center">
                  <p className="text-sm font-medium text-text-primary">
                    No watchlists yet.
                  </p>

                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    Create your first watchlist to start tracking
                    instruments.
                  </p>
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {watchlists.map((watchlist) => {
                    const isSelected =
                      watchlist.watchlist_id ===
                      selectedWatchlistId;

                    return (
                      <button
                        key={watchlist.watchlist_id}
                        type="button"
                        onClick={() =>
                          setSelectedWatchlistId(
                            watchlist.watchlist_id,
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
                              {watchlist.name}
                            </p>

                            <p className="mt-1 text-xs text-text-muted">
                              Updated{" "}
                              {formatTimestamp(
                                watchlist.updated_at,
                              )}
                            </p>
                          </div>

                          <Badge
                            variant={
                              isSelected ? "info" : "neutral"
                            }
                          >
                            {watchlist.item_count}
                          </Badge>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </Card>
          </section>

          <Card
            title={
              selectedWatchlist
                ? selectedWatchlist.name
                : "Selected watchlist"
            }
            description={
              selectedListSummary
                ? `${selectedListSummary.item_count} tracked instrument${
                    selectedListSummary.item_count === 1
                      ? ""
                      : "s"
                  }.`
                : "Select or create a watchlist to manage its instruments."
            }
          >
            {!selectedWatchlistId ? (
              <div className="rounded-md border border-border bg-surface-subtle px-5 py-10 text-center">
                <p className="text-sm font-medium text-text-primary">
                  Select a watchlist
                </p>

                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  Your selected watchlist and its tracked instruments
                  will appear here.
                </p>
              </div>
            ) : isDetailLoading ? (
              <div className="flex flex-col gap-3">
                {[1, 2, 3].map((item) => (
                  <div
                    key={item}
                    className="h-20 animate-pulse rounded-md bg-surface-muted"
                  />
                ))}
              </div>
            ) : detailErrorMessage ? (
              <div className="flex flex-col gap-4">
                <p className="text-sm leading-6 text-text-secondary">
                  {detailErrorMessage}
                </p>

                <div>
                  <Button
                    onClick={() =>
                      selectedWatchlistId &&
                      void loadSelectedWatchlist(
                        selectedWatchlistId,
                      )
                    }
                  >
                    Try again
                  </Button>
                </div>
              </div>
            ) : selectedWatchlist ? (
              <div className="flex flex-col gap-6">
                <div className="flex flex-col gap-4 rounded-md border border-border bg-surface-subtle p-4 lg:flex-row lg:items-end lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <Input
                      label="Add instrument by ticker"
                      value={ticker}
                      onChange={(event) => {
                        setTicker(event.target.value);
                        setInstrumentPreview(null);
                        setAddErrorMessage(null);
                      }}
                      placeholder="e.g. NVDA"
                      autoCapitalize="characters"
                      autoComplete="off"
                      maxLength={32}
                      disabled={isAdding}
                      error={addErrorMessage ?? undefined}
                    />

                    {instrumentPreview && (
                      <div className="mt-3 rounded-md border border-border bg-surface px-3 py-3">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <p className="font-mono text-sm font-semibold text-text-primary">
                              {instrumentPreview.symbol}
                            </p>

                            <p className="mt-1 text-sm text-text-secondary">
                              {instrumentPreview.name}
                            </p>
                          </div>

                          <div className="text-left text-xs text-text-muted sm:text-right">
                            <p>{instrumentPreview.exchange}</p>

                            <p className="mt-1">
                              {formatLabel(
                                instrumentPreview.asset_class,
                              )}{" "}
                              · {instrumentPreview.currency}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={() =>
                        void handleResolveInstrument()
                      }
                      disabled={isAdding || !ticker.trim()}
                    >
                      {isAdding && !instrumentPreview
                        ? "Resolving"
                        : "Resolve ticker"}
                    </Button>

                    <Button
                      onClick={() =>
                        void handleAddInstrument()
                      }
                      disabled={
                        isAdding ||
                        instrumentPreview === null
                      }
                    >
                      {isAdding && instrumentPreview
                        ? "Adding"
                        : "Add to watchlist"}
                    </Button>
                  </div>
                </div>

                {selectedWatchlist.items.length === 0 ? (
                  <div className="rounded-md border border-border bg-surface-subtle px-5 py-10 text-center">
                    <p className="text-sm font-medium text-text-primary">
                      This watchlist is empty.
                    </p>

                    <p className="mt-2 text-sm leading-6 text-text-secondary">
                      Resolve an active ticker above and add it to this
                      watchlist.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[720px] border-separate border-spacing-0">
                      <thead>
                        <tr className="text-left">
                          <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Instrument
                          </th>

                          <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Exchange
                          </th>

                          <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Asset class
                          </th>

                          <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Currency
                          </th>

                          <th className="border-b border-border px-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Added
                          </th>

                          <th className="border-b border-border px-3 py-3 text-right text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                            Action
                          </th>
                        </tr>
                      </thead>

                      <tbody>
                        {selectedWatchlist.items.map((item) => (
                          <tr key={item.item_id}>
                            <td className="border-b border-border px-3 py-4">
                              <div>
                                <p className="font-mono text-sm font-semibold text-text-primary">
                                  {item.symbol}
                                </p>

                                <p className="mt-1 text-sm text-text-secondary">
                                  {item.name}
                                </p>
                              </div>
                            </td>

                            <td className="border-b border-border px-3 py-4 text-sm text-text-secondary">
                              {item.exchange}
                            </td>

                            <td className="border-b border-border px-3 py-4 text-sm text-text-secondary">
                              {formatLabel(item.asset_class)}
                            </td>

                            <td className="border-b border-border px-3 py-4 text-sm text-text-secondary">
                              {item.currency}
                            </td>

                            <td className="border-b border-border px-3 py-4 text-sm text-text-secondary">
                              {formatTimestamp(item.added_at)}
                            </td>

                            <td className="border-b border-border px-3 py-4 text-right">
                              <Button
                                variant="ghost"
                                onClick={() =>
                                  void handleRemoveItem(item)
                                }
                                disabled={
                                  removingItemId ===
                                  item.item_id
                                }
                              >
                                {removingItemId ===
                                item.item_id
                                  ? "Removing"
                                  : "Remove"}
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {deleteErrorMessage && (
                  <p
                    className="text-sm leading-6 text-negative"
                    role="alert"
                  >
                    {deleteErrorMessage}
                  </p>
                )}

                <div className="flex flex-col gap-4 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                      Watchlist metadata
                    </p>

                    <p className="mt-1 text-sm text-text-secondary">
                      Created{" "}
                      {formatTimestamp(
                        selectedWatchlist.created_at,
                      )}
                    </p>
                  </div>

                  <Button
                    variant="danger"
                    onClick={() =>
                      void handleDeleteWatchlist()
                    }
                    disabled={deletingWatchlist}
                  >
                    {deletingWatchlist
                      ? "Deleting watchlist"
                      : "Delete watchlist"}
                  </Button>
                </div>
              </div>
            ) : null}
          </Card>

          <Card
            title="Watchlist behavior"
            description="How persisted instruments are handled in this workspace."
          >
            <div className="grid gap-4 md:grid-cols-3">
              <BehaviorNote
                title="Database-backed"
                description="Watchlists and memberships are loaded from the authenticated MarketThread API."
              />

              <BehaviorNote
                title="Canonical instruments"
                description="Ticker input is resolved to an existing active instrument before it can be added."
              />

              <BehaviorNote
                title="Idempotent membership"
                description="Adding an instrument already tracked by the selected watchlist does not create a duplicate item."
              />
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function BehaviorNote({
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

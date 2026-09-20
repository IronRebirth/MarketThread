"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/auth-provider";
import {
  fetchNotifications,
  markNotificationRead,
  NotificationsApiError,
  syncNotifications,
  type WatchlistNotification,
} from "../../lib/notifications-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

function getErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (error instanceof NotificationsApiError) {
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

function formatConfidence(value: number) {
  return Math.round(value * 100) + "%";
}

function getDirectionVariant(
  direction: string,
): "positive" | "negative" | "neutral" {
  const normalized = direction.trim().toLowerCase();

  if (
    normalized === "positive" ||
    normalized === "upside" ||
    normalized === "favorable"
  ) {
    return "positive";
  }

  if (
    normalized === "negative" ||
    normalized === "downside" ||
    normalized === "unfavorable"
  ) {
    return "negative";
  }

  return "neutral";
}

export function NotificationInbox() {
  const { isLoading: isAuthLoading, isAuthenticated } = useAuth();

  const [notifications, setNotifications] = useState<
    WatchlistNotification[]
  >([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [markingReadId, setMarkingReadId] = useState<string | null>(
    null,
  );

  const loadNotifications = useCallback(
    async (filterUnread: boolean) => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const response = await fetchNotifications(
          100,
          filterUnread,
        );

        setNotifications(response.notifications);
        setUnreadCount(response.unread_count);
      } catch (error) {
        setNotifications([]);
        setUnreadCount(0);
        setErrorMessage(
          getErrorMessage(
            error,
            "Notifications could not be loaded.",
          ),
        );
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const synchronizeAndLoad = useCallback(async () => {
    setIsSyncing(true);
    setErrorMessage(null);

    try {
      await syncNotifications();
      await loadNotifications(unreadOnly);

      window.dispatchEvent(
        new Event("marketthread-notifications-updated"),
      );
    } catch (error) {
      setErrorMessage(
        getErrorMessage(
          error,
          "New notifications could not be synchronized.",
        ),
      );
    } finally {
      setIsSyncing(false);
    }
  }, [loadNotifications, unreadOnly]);

  useEffect(() => {
    if (isAuthLoading || !isAuthenticated) {
      return;
    }

    queueMicrotask(() => {
      void synchronizeAndLoad();
    });
  }, [isAuthLoading, isAuthenticated, synchronizeAndLoad]);

  useEffect(() => {
    if (isAuthLoading || !isAuthenticated) {
      return;
    }

    const handleNotificationUpdate = () => {
      void loadNotifications(unreadOnly);
    };

    window.addEventListener(
      "marketthread-notifications-updated",
      handleNotificationUpdate,
    );

    return () => {
      window.removeEventListener(
        "marketthread-notifications-updated",
        handleNotificationUpdate,
      );
    };
  }, [isAuthLoading, isAuthenticated, loadNotifications, unreadOnly]);

  const visibleSummary = useMemo(() => {
    if (unreadOnly) {
      return (
        notifications.length +
        " unread notification" +
        (notifications.length === 1 ? "" : "s")
      );
    }

    return (
      notifications.length +
      " notification" +
      (notifications.length === 1 ? "" : "s")
    );
  }, [notifications.length, unreadOnly]);

  const handleMarkRead = async (
    notification: WatchlistNotification,
  ) => {
    if (notification.read_at !== null) {
      return;
    }

    setMarkingReadId(notification.notification_id);
    setErrorMessage(null);

    try {
      const updated = await markNotificationRead(
        notification.notification_id,
      );

      setNotifications((current) =>
        current.map((item) =>
          item.notification_id === updated.notification_id
            ? updated
            : item,
        ),
      );

      setUnreadCount((current) => Math.max(0, current - 1));

      window.dispatchEvent(
        new Event("marketthread-notifications-updated"),
      );
    } catch (error) {
      setErrorMessage(
        getErrorMessage(
          error,
          "The notification could not be marked as read.",
        ),
      );
    } finally {
      setMarkingReadId(null);
    }
  };

  const handleFilterChange = (nextUnreadOnly: boolean) => {
    setUnreadOnly(nextUnreadOnly);
    void loadNotifications(nextUnreadOnly);
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
            <Badge variant="info">Notifications</Badge>
          </div>
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Notification inbox
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Review alert-rule matches generated from persisted market
              intelligence for your watchlists.
            </p>
          </div>
        </header>
        <AuthRequiredPrompt nextPath="/notifications" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Notifications</Badge>
          <Badge variant={unreadCount > 0 ? "warning" : "positive"}>
            {unreadCount} unread
          </Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">
              MarketThread
            </p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Notification inbox
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Review alert-rule matches generated from persisted market
              intelligence for your watchlists.
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() => void synchronizeAndLoad()}
            disabled={isSyncing}
          >
            {isSyncing ? "Checking for alerts" : "Check for new alerts"}
          </Button>
        </div>
      </header>

      {errorMessage && (
        <Card
          title="Notifications unavailable"
          description="MarketThread could not complete the requested notification operation."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button
                onClick={() => void loadNotifications(unreadOnly)}
              >
                Try again
              </Button>
            </div>
          </div>
        </Card>
      )}

      {!errorMessage && (
        <Card
          title={unreadOnly ? "Unread notifications" : "All notifications"}
          description={
            visibleSummary +
            ". Notifications are persisted to your account."
          }
        >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
            <div className="flex gap-2">
              <Button
                variant={unreadOnly ? "secondary" : "primary"}
                onClick={() => handleFilterChange(false)}
              >
                All
              </Button>

              <Button
                variant={unreadOnly ? "primary" : "secondary"}
                onClick={() => handleFilterChange(true)}
              >
                Unread
              </Button>
            </div>

            <p className="text-xs text-text-muted">
              New alert deliveries are created only when they match an
              enabled watchlist rule.
            </p>
          </div>

          {isLoading ? (
            <div className="flex flex-col gap-3 pt-5">
              {[1, 2, 3].map((item) => (
                <div
                  key={item}
                  className="h-32 animate-pulse rounded-md bg-surface-muted"
                />
              ))}
            </div>
          ) : notifications.length === 0 ? (
            <div className="rounded-md border border-border bg-surface-subtle px-5 py-12 text-center">
              <p className="text-sm font-medium text-text-primary">
                {unreadOnly
                  ? "No unread notifications."
                  : "No notifications yet."}
              </p>

              <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-text-secondary">
                {unreadOnly
                  ? "All persisted notifications have been reviewed."
                  : "Create an enabled alert rule on a watchlist, then check for new alerts when persisted intelligence is available."}
              </p>

              {!unreadOnly && (
                <div className="mt-5">
                  <Link
                    href="/watchlists"
                    className="text-sm font-medium text-brand hover:underline"
                  >
                    Open watchlists
                  </Link>
                </div>
              )}
            </div>
          ) : (
            <div className="divide-y divide-border">
              {notifications.map((notification) => {
                const isUnread = notification.read_at === null;

                return (
                  <article
                    key={notification.notification_id}
                    className={[
                      "py-5 first:pt-5 last:pb-0",
                      isUnread ? "bg-brand/5" : "",
                    ].join(" ")}
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="info">
                            {notification.symbol}
                          </Badge>

                          <Badge variant="neutral">
                            {formatLabel(notification.event_type)}
                          </Badge>

                          <Badge
                            variant={getDirectionVariant(
                              notification.direction,
                            )}
                          >
                            {formatLabel(notification.direction)}
                          </Badge>

                          {isUnread && (
                            <Badge variant="warning">Unread</Badge>
                          )}
                        </div>

                        <h3 className="mt-3 text-base font-semibold text-text-primary">
                          {notification.title}
                        </h3>

                        <p className="mt-2 text-sm leading-6 text-text-secondary">
                          {notification.message}
                        </p>

                        <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-text-muted">
                          <span>
                            Rule: {notification.rule_name}
                          </span>

                          <span>
                            Confidence:{" "}
                            {formatConfidence(
                              notification.confidence,
                            )}
                          </span>

                          <span>
                            {formatTimestamp(
                              notification.created_at,
                            )}
                          </span>
                        </div>
                      </div>

                      <div className="flex shrink-0 flex-wrap gap-2 lg:flex-col lg:items-stretch">
                        <Link
                          href="/watchlists"
                          className="inline-flex min-h-10 items-center justify-center rounded-md border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-muted hover:text-text-primary"
                        >
                          View watchlists
                        </Link>

                        {isUnread && (
                          <Button
                            variant="secondary"
                            onClick={() =>
                              void handleMarkRead(notification)
                            }
                            disabled={
                              markingReadId ===
                              notification.notification_id
                            }
                          >
                            {markingReadId ===
                            notification.notification_id
                              ? "Marking read"
                              : "Mark as read"}
                          </Button>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </Card>
      )}

      <Card
        title="Notification behavior"
        description="How MarketThread handles alert deliveries in this inbox."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <BehaviorNote
            title="Evidence-backed"
            description="Notifications reference existing alert intelligence rather than creating a separate prediction."
          />

          <BehaviorNote
            title="Deduplicated"
            description="The same alert-rule and alert combination produces one persisted notification for your account."
          />

          <BehaviorNote
            title="Persistent"
            description="Read state is stored in PostgreSQL and survives page refreshes and new sessions."
          />
        </div>
      </Card>
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

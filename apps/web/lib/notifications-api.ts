import { authenticatedFetch } from "./auth-api";

export type WatchlistNotification = {
  notification_id: string;
  watchlist_id: string;
  alert_rule_id: string;
  alert_id: string;
  symbol: string;
  rule_name: string;
  title: string;
  message: string;
  event_type: string;
  direction: string;
  confidence: number;
  created_at: string;
  read_at: string | null;
};

export type WatchlistNotificationsResponse = {
  notifications: WatchlistNotification[];
  returned_count: number;
  unread_count: number;
};

export type WatchlistNotificationSyncResponse = {
  created_count: number;
  existing_count: number;
  matched_alert_count: number;
};

export class NotificationsApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "NotificationsApiError";
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function readErrorMessage(response: Response): Promise<string> {
  const detail = await response.text();

  if (!detail) {
    return "Notifications request failed (" + response.status + ")";
  }

  try {
    const payload = JSON.parse(detail) as { detail?: unknown };

    if (typeof payload.detail === "string") {
      return payload.detail;
    }

    if (
      Array.isArray(payload.detail) &&
      payload.detail.every(
        (item) =>
          typeof item === "object" &&
          item !== null &&
          "msg" in item &&
          typeof item.msg === "string",
      )
    ) {
      return payload.detail.map((item) => item.msg).join(" ");
    }
  } catch {
    // Fall back to the raw response body when it is not JSON.
  }

  return detail;
}

async function requestJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const response = await authenticatedFetch(input, init);

  if (!response.ok) {
    throw new NotificationsApiError(
      response.status,
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as T;
}

export async function fetchNotifications(
  limit = 100,
  unreadOnly = false,
): Promise<WatchlistNotificationsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
  });

  if (unreadOnly) {
    params.set("unread_only", "true");
  }

  return requestJson<WatchlistNotificationsResponse>(
    API_BASE_URL + "/notifications?" + params.toString(),
  );
}

export async function syncNotifications(): Promise<WatchlistNotificationSyncResponse> {
  return requestJson<WatchlistNotificationSyncResponse>(
    API_BASE_URL + "/notifications/sync",
    {
      method: "POST",
    },
  );
}

export async function markNotificationRead(
  notificationId: string,
): Promise<WatchlistNotification> {
  const response = await requestJson<{
    notification: WatchlistNotification;
  }>(
    API_BASE_URL +
      "/notifications/" +
      encodeURIComponent(notificationId) +
      "/read",
    {
      method: "PATCH",
    },
  );

  return response.notification;
}

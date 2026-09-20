"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth/auth-provider";
import { fetchNotifications } from "../../lib/notifications-api";
import { ThemeSwitcher } from "../ui/theme-switcher";
import { Button } from "../ui/button";

interface TopbarProps {
  onMenuClick: () => void;
}

function getInitials(email: string) {
  const localPart = email.split("@")[0]?.trim();

  if (!localPart) return "MT";

  const parts = localPart.split(/[._-]+/).filter(Boolean);

  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }

  return localPart.slice(0, 2).toUpperCase();
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const [search, setSearch] = useState("");
  const [unreadCount, setUnreadCount] = useState(0);
  const { user, isLoading, logout } = useAuth();

  const initials = useMemo(
    () => (user ? getInitials(user.email) : "MT"),
    [user],
  );

  useEffect(() => {
    if (!user) {
      setUnreadCount(0);
      return;
    }

    let cancelled = false;

    const loadUnreadCount = async () => {
      try {
        const response = await fetchNotifications(1, true);
        if (!cancelled) setUnreadCount(response.unread_count);
      } catch {
        if (!cancelled) setUnreadCount(0);
      }
    };

    void loadUnreadCount();

    const handleNotificationUpdate = () => {
      void loadUnreadCount();
    };

    window.addEventListener("marketthread-notifications-updated", handleNotificationUpdate);

    return () => {
      cancelled = true;
      window.removeEventListener("marketthread-notifications-updated", handleNotificationUpdate);
    };
  }, [user]);

  return (
    <header className="flex min-h-16 items-center gap-4 border-b border-border bg-surface px-4 sm:px-6">
      <button type="button" onClick={onMenuClick} className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-border text-text-secondary hover:bg-surface-muted hover:text-text-primary lg:hidden" aria-label="Open navigation">
        <span aria-hidden="true" className="text-lg">☰</span>
      </button>

      <div className="min-w-0 flex-1">
        <label htmlFor="global-search" className="sr-only">Search MarketThread</label>
        <input
          id="global-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search markets, companies, events, or news"
          className="h-10 w-full max-w-2xl rounded-md border border-border bg-surface-subtle px-3 text-sm text-text-primary outline-none placeholder:text-text-muted focus:border-brand focus:ring-2 focus:ring-brand/20"
        />
      </div>

      {user && (
        <Link
          href="/notifications"
          className="relative inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-border text-text-secondary hover:bg-surface-muted hover:text-text-primary"
          aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications"}
          title="Notifications"
        >
          <span aria-hidden="true" className="text-lg">♢</span>
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-negative px-1 text-[10px] font-semibold text-text-inverse">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </Link>
      )}

      <div className="hidden shrink-0 sm:block"><ThemeSwitcher /></div>

      <button type="button" className="hidden h-10 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm font-medium text-text-secondary hover:bg-surface-muted hover:text-text-primary sm:inline-flex">
        <span className="h-2 w-2 rounded-full bg-positive" aria-hidden="true" />
        <span>Markets open</span>
      </button>

      {user ? (
        <div className="hidden items-center gap-3 sm:flex">
          <div className="max-w-48 truncate text-right">
            <p className="truncate text-xs font-medium text-text-primary">{user.email}</p>
            <p className="text-xs text-text-muted">Authenticated</p>
          </div>

          <Button variant="ghost" className="min-h-10 px-3" onClick={logout}>Sign out</Button>

          <div className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-semibold text-text-inverse" aria-label={`Account for ${user.email}`}>
            {initials}
          </div>
        </div>
      ) : (
        <div className="hidden sm:block">
          <a href="/login" className="inline-flex h-10 items-center rounded-md border border-border bg-surface px-3 text-sm font-medium text-text-secondary hover:bg-surface-muted hover:text-text-primary">
            {isLoading ? "Loading" : "Sign in"}
          </a>
        </div>
      )}

      <div className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-semibold text-text-inverse sm:hidden">
        {initials}
      </div>
    </header>
  );
}

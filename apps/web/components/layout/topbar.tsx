"use client";

import { useState } from "react";

import { ThemeSwitcher } from "../ui/theme-switcher";

interface TopbarProps {
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const [search, setSearch] = useState("");

  return (
    <header className="flex min-h-16 items-center gap-4 border-b border-border bg-surface px-4 sm:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-border text-text-secondary hover:bg-surface-muted hover:text-text-primary lg:hidden"
        aria-label="Open navigation"
      >
        <span aria-hidden="true" className="text-lg">
          ☰
        </span>
      </button>

      <div className="min-w-0 flex-1">
        <label htmlFor="global-search" className="sr-only">
          Search MarketThread
        </label>

        <input
          id="global-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search markets, companies, events, or news"
          className="h-10 w-full max-w-2xl rounded-md border border-border bg-surface-subtle px-3 text-sm text-text-primary outline-none placeholder:text-text-muted focus:border-brand focus:ring-2 focus:ring-brand/20"
        />
      </div>

      <div className="hidden shrink-0 sm:block">
        <ThemeSwitcher />
      </div>

      <button
        type="button"
        className="hidden h-10 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm font-medium text-text-secondary hover:bg-surface-muted hover:text-text-primary sm:inline-flex"
      >
        <span
          className="h-2 w-2 rounded-full bg-positive"
          aria-hidden="true"
        />

        <span>Markets open</span>
      </button>

      <button
        type="button"
        className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand text-sm font-semibold text-text-inverse"
        aria-label="Open account menu"
      >
        MT
      </button>
    </header>
  );
}
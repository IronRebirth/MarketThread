"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "../auth/auth-provider";
import { primaryNavigation } from "./navigation";

interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <aside className="flex h-full w-72 flex-col border-r border-border bg-surface">
      <div className="border-b border-border px-5 py-5">
        <Link
          href="/"
          onClick={onNavigate}
          className="group inline-flex flex-col"
        >
          <span className="text-lg font-semibold tracking-tight text-text-primary">
            MarketThread
          </span>

          <span className="mt-1 text-xs text-text-muted">
            Global market intelligence
          </span>
        </Link>
      </div>

      <nav
        aria-label="Primary navigation"
        className="flex-1 overflow-y-auto px-3 py-4"
      >
        <div className="space-y-1">
          {primaryNavigation.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                aria-current={isActive ? "page" : undefined}
                className={[
                  "block rounded-md px-3 py-2.5 transition-colors",
                  isActive
                    ? "bg-brand-soft text-brand"
                    : "text-text-secondary hover:bg-surface-muted hover:text-text-primary",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span className="block text-sm font-medium">{item.label}</span>

                <span
                  className={[
                    "mt-0.5 block text-xs leading-5",
                    isActive ? "text-brand/80" : "text-text-muted",
                  ].join(" ")}
                >
                  {item.description}
                </span>
              </Link>
            );
          })}
        </div>
          {user?.role === "admin" && (
            <Link
              href="/admin"
              onClick={onNavigate}
              aria-current={pathname.startsWith("/admin") ? "page" : undefined}
              className={[
                "block rounded-md px-3 py-2.5 transition-colors",
                pathname.startsWith("/admin")
                  ? "bg-brand-soft text-brand"
                  : "text-text-secondary hover:bg-surface-muted hover:text-text-primary",
              ].join(" ")}
            >
              <span className="block text-sm font-medium">Administration</span>
              <span className="mt-0.5 block text-xs leading-5 text-text-muted">
                System operations and audit activity
              </span>
            </Link>
          )}
      </nav>

      <div className="border-t border-border px-4 py-4">
        <div className="rounded-md bg-surface-subtle px-3 py-3">
          <p className="text-xs font-medium text-text-primary">
            Intelligence platform
          </p>

          <p className="mt-1 text-xs leading-5 text-text-muted">
            Evidence, impact, risk, and confidence in one workflow.
          </p>
        </div>
      </div>
    </aside>
  );
}
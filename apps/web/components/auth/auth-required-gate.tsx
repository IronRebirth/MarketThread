"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useAuth } from "./auth-provider";

interface AuthRequiredGateProps {
  nextPath: string;
  children: ReactNode;
}

export function AuthRequiredGate({
  nextPath,
  children,
}: AuthRequiredGateProps) {
  const { isLoading, isAuthenticated } = useAuth();

  if (isLoading) {
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
        <div className="w-full max-w-2xl rounded-lg border border-border bg-surface p-6 shadow-sm sm:p-8">
          <p className="text-lg font-semibold text-text-primary">
            Sign in required
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            Research answers can include user-scoped portfolio context, so
            this workspace requires authentication.
          </p>

          <Link
            href={`/login?next=${encodeURIComponent(nextPath)}`}
            className="mt-5 inline-flex font-semibold text-brand hover:underline"
          >
            Sign in to continue
          </Link>
        </div>
      </div>
    );
  }

  return children;
}

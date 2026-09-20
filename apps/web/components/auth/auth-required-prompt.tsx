"use client";

import Link from "next/link";

interface AuthRequiredPromptProps {
  nextPath: string;
}

export function AuthRequiredPrompt({
  nextPath,
}: AuthRequiredPromptProps) {
  const encodedNextPath = encodeURIComponent(nextPath);

  return (
    <div className="rounded-lg border border-border bg-surface p-6 shadow-sm sm:p-8">
      <p className="text-lg font-semibold text-text-primary">
        Sign in required
      </p>

      <p className="mt-2 text-sm leading-6 text-text-secondary">
        Sign in or create an account to access this personalized MarketThread
        workspace.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Link
          href={`/login?next=${encodedNextPath}`}
          className="inline-flex h-10 items-center rounded-md bg-brand px-4 text-sm font-medium text-text-inverse hover:bg-brand-hover"
        >
          Sign in
        </Link>

        <Link
          href={`/register?next=${encodedNextPath}`}
          className="inline-flex h-10 items-center rounded-md border border-border px-4 text-sm font-medium text-text-secondary hover:bg-surface-muted hover:text-text-primary"
        >
          Create account
        </Link>
      </div>
    </div>
  );
}

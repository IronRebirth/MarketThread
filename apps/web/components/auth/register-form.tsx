"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AuthApiError } from "../../lib/auth-api";
import { useAuth } from "./auth-provider";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";

function getErrorMessage(error: unknown) {
  if (error instanceof AuthApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "The account could not be created.";
}

function getSafeNextPath() {
  if (typeof window === "undefined") {
    return "/";
  }

  const next = new URLSearchParams(
    window.location.search,
  ).get("next");

  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return "/";
  }

  return next;
}

export function RegisterForm() {
  const router = useRouter();
  const { register, login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(
    null,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    setErrorMessage(null);

    if (password !== confirmation) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      await register({
        email: email.trim(),
        password,
      });

      await login({
        email: email.trim(),
        password,
      });

      router.replace(getSafeNextPath());
      router.refresh();
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const nextPath = getSafeNextPath();

  return (
    <Card
      title="Create your MarketThread account"
      description="Set up an account for personalized watchlists and future portfolio intelligence."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {errorMessage && (
          <div
            role="alert"
            className="rounded-md border border-negative bg-negative-soft px-4 py-3"
          >
            <p className="text-sm leading-6 text-negative">
              {errorMessage}
            </p>
          </div>
        )}

        <label className="flex flex-col gap-2">
          <span className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Email
          </span>

          <Input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            required
          />
        </label>

        <label className="flex flex-col gap-2">
          <span className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Password
          </span>

          <Input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Minimum 8 characters"
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>

        <label className="flex flex-col gap-2">
          <span className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Confirm password
          </span>

          <Input
            type="password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder="Re-enter your password"
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>

        <Button type="submit" fullWidth disabled={isSubmitting}>
          {isSubmitting ? "Creating account" : "Create account"}
        </Button>

        <p className="text-center text-sm text-text-secondary">
          Already have an account?{" "}
          <Link
            href={`/login?next=${encodeURIComponent(nextPath)}`}
            className="font-medium text-brand hover:underline"
          >
            Sign in
          </Link>
        </p>
      </form>
    </Card>
  );
}

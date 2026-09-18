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

  return "The account could not be authenticated.";
}

export function LoginForm() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await login({
        email: email.trim(),
        password,
      });

      router.replace("/");
      router.refresh();
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card
      title="Sign in to MarketThread"
      description="Use your MarketThread account to access personalized research workspaces."
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
            placeholder="Enter your password"
            autoComplete="current-password"
            minLength={8}
            required
          />
        </label>

        <Button type="submit" fullWidth disabled={isSubmitting}>
          {isSubmitting ? "Signing in" : "Sign in"}
        </Button>

        <p className="text-center text-sm text-text-secondary">
          No account yet?{" "}
          <Link
            href="/register"
            className="font-medium text-brand hover:underline"
          >
            Create one
          </Link>
        </p>
      </form>
    </Card>
  );
}

import Link from "next/link";

import { LoginForm } from "../../components/auth/login-form";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <Link
            href="/"
            className="text-sm font-medium text-brand hover:underline"
          >
            MarketThread
          </Link>

          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-text-primary">
            Market intelligence, grounded in evidence
          </h1>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            Sign in to continue to your personalized workspace.
          </p>
        </div>

        <LoginForm />
      </div>
    </main>
  );
}

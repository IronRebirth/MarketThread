import Link from "next/link";

import { RegisterForm } from "../../components/auth/register-form";

export default function RegisterPage() {
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
            Create your MarketThread workspace
          </h1>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            Start building personalized research views and watchlists.
          </p>
        </div>

        <RegisterForm />
      </div>
    </main>
  );
}

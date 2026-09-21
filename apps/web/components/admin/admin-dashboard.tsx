"use client";

import { useEffect, useState } from "react";

import { useAuth } from "../auth/auth-provider";
import {
  fetchAdminAuditLogs,
  fetchAdminHealth,
  type AdminAuditLog,
  type AdminSystemHealth,
} from "../../lib/admin-api";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";

export function AdminDashboard() {
  const { isLoading, isAuthenticated, user } = useAuth();
  const [health, setHealth] = useState<AdminSystemHealth | null>(null);
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isLoading || !isAuthenticated || user?.role !== "admin") {
      return;
    }

    void Promise.all([fetchAdminHealth(), fetchAdminAuditLogs()])
      .then(([healthResponse, auditResponse]) => {
        setHealth(healthResponse);
        setLogs(auditResponse.entries);
      })
      .catch((reason: unknown) => {
        setError(
          reason instanceof Error
            ? reason.message
            : "Administration data is unavailable.",
        );
      });
  }, [isLoading, isAuthenticated, user?.role]);

  if (isLoading) {
    return (
      <p className="text-sm text-text-secondary">
        Restoring your MarketThread session…
      </p>
    );
  }

  if (!isAuthenticated) {
    return (
      <Card
        title="Sign in required"
        description="Administration is restricted to authenticated administrators."
      >
        <p className="text-sm text-text-secondary">
          Sign in with an administrator account to continue.
        </p>
      </Card>
    );
  }

  if (user?.role !== "admin") {
    return (
      <Card
        title="Administrator access required"
        description="This workspace is restricted to MarketThread administrators."
      >
        <p className="text-sm text-text-secondary">
          Your account does not have administrator privileges.
        </p>
      </Card>
    );
  }

  if (error) {
    return (
      <Card title="Administration unavailable">
        <p className="text-sm text-text-secondary">{error}</p>
      </Card>
    );
  }

  if (!health) {
    return (
      <p className="text-sm text-text-secondary">
        Loading administration status…
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <Badge variant="info">Administration</Badge>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
          System operations
        </h1>
        <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
          Monitor provider availability, background-job readiness, persisted
          data coverage, and administrative audit activity.
        </p>
      </header>

      <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <Card title="Database">
          <p className="text-2xl font-semibold text-text-primary">
            {health.database}
          </p>
        </Card>
        <Card title="Background jobs">
          <p className="text-2xl font-semibold text-text-primary">
            {health.background_jobs}
          </p>
        </Card>
        <Card title="Audit entries">
          <p className="text-2xl font-semibold text-text-primary">
            {health.audit_log_entries}
          </p>
        </Card>
        <Card title="Last checked">
          <p className="text-sm text-text-secondary">
            {new Date(health.checked_at).toLocaleString()}
          </p>
        </Card>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <Card
          title="Provider monitoring"
          description="Current configuration and health signals."
        >
          <div className="flex flex-col gap-3">
            {health.providers.map((provider) => (
              <div
                key={provider.name}
                className="flex items-start justify-between gap-4 border-b border-border pb-3 last:border-0 last:pb-0"
              >
                <div>
                  <p className="font-medium text-text-primary">
                    {provider.name}
                  </p>
                  <p className="text-sm text-text-secondary">
                    {provider.detail}
                  </p>
                </div>
                <Badge
                  variant={
                    provider.status === "healthy" ||
                    provider.status === "configured"
                      ? "positive"
                      : provider.status === "degraded"
                        ? "warning"
                        : "negative"
                  }
                >
                  {provider.status}
                </Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card
          title="Persisted data quality"
          description="Record counts across core intelligence domains."
        >
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(health.data_quality).map(([key, value]) => (
              <div key={key}>
                <p className="text-sm capitalize text-text-secondary">
                  {key.replaceAll("_", " ")}
                </p>
                <p className="text-xl font-semibold text-text-primary">
                  {value}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <Card
        title="Recent audit activity"
        description="Administrative access is recorded for operational accountability."
      >
        <div className="flex flex-col gap-3">
          {logs.length === 0 ? (
            <p className="text-sm text-text-secondary">
              No audit entries yet.
            </p>
          ) : (
            logs.slice(0, 10).map((log) => (
              <div
                key={log.id}
                className="border-b border-border pb-3 last:border-0 last:pb-0"
              >
                <p className="font-medium text-text-primary">{log.action}</p>
                <p className="text-sm text-text-secondary">
                  {log.resource_type} ·{" "}
                  {new Date(log.created_at).toLocaleString()}
                </p>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}

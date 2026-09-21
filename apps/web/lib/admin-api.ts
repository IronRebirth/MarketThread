import { authenticatedFetch } from "./auth-api";

export interface AdminProviderStatus {
  name: string;
  status: string;
  detail: string;
}

export interface AdminSystemHealth {
  database: string;
  providers: AdminProviderStatus[];
  background_jobs: string;
  data_quality: Record<string, number>;
  audit_log_entries: number;
  checked_at: string;
}

export interface AdminAuditLog {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

interface AuditResponse {
  entries: AdminAuditLog[];
  total: number;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function request<T>(path: string): Promise<T> {
  const response = await authenticatedFetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(body.detail ?? "Administration request failed.");
  }

  return (await response.json()) as T;
}

export function fetchAdminHealth(): Promise<AdminSystemHealth> {
  return request<AdminSystemHealth>("/admin/health");
}

export function fetchAdminAuditLogs(): Promise<AuditResponse> {
  return request<AuditResponse>("/admin/audit-logs?limit=50");
}

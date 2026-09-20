import { AppShell } from "../../components/layout/app-shell";
import { AdminDashboard } from "../../components/admin/admin-dashboard";

export default function AdminPage() {
  return (
    <AppShell>
      <AdminDashboard />
    </AppShell>
  );
}

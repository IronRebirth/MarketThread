import { AppShell } from "../../components/layout/app-shell";
import { AuthRequiredGate } from "../../components/auth/auth-required-gate";
import { NotificationInbox } from "../../components/notifications/notification-inbox";

export default function NotificationsPage() {
  return (
    <AppShell>
      <AuthRequiredGate nextPath="/notifications">
        <NotificationInbox />
      </AuthRequiredGate>
    </AppShell>
  );
}

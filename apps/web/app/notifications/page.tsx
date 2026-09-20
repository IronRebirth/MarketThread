import { AppShell } from "../../components/layout/app-shell";
import { AuthRequiredPrompt } from "../../components/auth/auth-required-prompt";
import { useAuth } from "../../components/auth/auth-provider";
import { NotificationInbox } from "../../components/notifications/notification-inbox";

export default function NotificationsPage() {
  return (
    <AppShell>
      <NotificationInbox />
    </AppShell>
  );
}

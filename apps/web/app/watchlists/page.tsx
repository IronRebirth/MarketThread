import { AppShell } from "../../components/layout/app-shell";
import { AuthRequiredPrompt } from "../../components/auth/auth-required-prompt";
import { useAuth } from "../../components/auth/auth-provider";
import { WatchlistDashboard } from "../../components/watchlists/watchlist-dashboard";

export default function WatchlistsPage() {
  return (
    <AppShell>
      <WatchlistDashboard />
    </AppShell>
  );
}

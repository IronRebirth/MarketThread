import { AppShell } from "../../components/layout/app-shell";
import { AuthRequiredGate } from "../../components/auth/auth-required-gate";
import { WatchlistDashboard } from "../../components/watchlists/watchlist-dashboard";

export default function WatchlistsPage() {
  return (
    <AppShell>
      <AuthRequiredGate nextPath="/watchlists">
        <WatchlistDashboard />
      </AuthRequiredGate>
    </AppShell>
  );
}

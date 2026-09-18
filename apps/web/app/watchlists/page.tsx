import { AppShell } from "../../components/layout/app-shell";
import { WatchlistDashboard } from "../../components/watchlists/watchlist-dashboard";

export default function WatchlistsPage() {
  return (
    <AppShell>
      <WatchlistDashboard />
    </AppShell>
  );
}

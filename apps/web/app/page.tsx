import { AppShell } from "../components/layout/app-shell";
import { MarketIntelligenceDashboard } from "../components/intelligence/market-intelligence-dashboard";

export default function Home() {
  return (
    <AppShell>
      <MarketIntelligenceDashboard />
    </AppShell>
  );
}

import { AppShell } from "../../components/layout/app-shell";
import { BacktestDashboard } from "../../components/backtesting/backtest-dashboard";

export default function BacktestsPage() {
  return (
    <AppShell>
      <BacktestDashboard />
    </AppShell>
  );
}

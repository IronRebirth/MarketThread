import { StockResearchDashboard } from "../../../components/stocks/stock-research-dashboard";
import { AppShell } from "../../../components/layout/app-shell";

export default async function StockResearchPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = await params;

  return (
    <AppShell>
      <StockResearchDashboard initialSymbol={decodeURIComponent(symbol)} />
    </AppShell>
  );
}

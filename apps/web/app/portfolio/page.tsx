import { AppShell } from "../../components/layout/app-shell";
import { AuthRequiredGate } from "../../components/auth/auth-required-gate";
import { PortfolioDashboard } from "../../components/portfolio/portfolio-dashboard";

export default function PortfolioPage() {
  return (
    <AppShell>
      <AuthRequiredGate nextPath="/portfolio">
        <PortfolioDashboard />
      </AuthRequiredGate>
    </AppShell>
  );
}

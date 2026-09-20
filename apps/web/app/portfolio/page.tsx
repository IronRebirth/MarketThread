import { AppShell } from "../../components/layout/app-shell";
import { AuthRequiredPrompt } from "../../components/auth/auth-required-prompt";
import { useAuth } from "../../components/auth/auth-provider";
import { PortfolioDashboard } from "../../components/portfolio/portfolio-dashboard";

export default function PortfolioPage() {
  return (
    <AppShell>
      <PortfolioDashboard />
    </AppShell>
  );
}

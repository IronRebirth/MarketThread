import { AppShell } from "../components/layout/app-shell";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";

const metrics = [
  {
    label: "Market signal",
    value: "Positive",
    variant: "positive" as const,
  },
  {
    label: "Confidence",
    value: "78%",
    variant: "info" as const,
  },
  {
    label: "Risk level",
    value: "Moderate",
    variant: "warning" as const,
  },
];

export default function Home() {
  return (
    <AppShell>
      <div className="flex flex-col gap-8">
        <header className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">Application shell</Badge>
            <Badge variant="neutral">Development</Badge>
          </div>

          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Global market intelligence
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              The shared product shell for market intelligence, news,
              event analysis, company research, portfolio intelligence, and
              evidence-driven recommendations.
            </p>
          </div>
        </header>

        <section className="grid gap-5 md:grid-cols-3">
          {metrics.map((metric) => (
            <Card key={metric.label}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm text-text-secondary">{metric.label}</p>

                  <p className="mt-2 text-2xl font-semibold text-text-primary">
                    {metric.value}
                  </p>
                </div>

                <Badge variant={metric.variant}>{metric.value}</Badge>
              </div>
            </Card>
          ))}
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
          <Card
            title="Intelligence workspace"
            description="The main content area is intentionally neutral so individual product modules can own their information architecture."
          >
            <div className="space-y-5">
              <div>
                <p className="text-sm font-semibold text-text-primary">
                  What happened?
                </p>

                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  A hypothetical global development has increased attention
                  across several market sectors.
                </p>
              </div>

              <div>
                <p className="text-sm font-semibold text-text-primary">
                  Why does it matter?
                </p>

                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  MarketThread will connect events, evidence, company impact,
                  confidence, and risk inside this workspace.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge variant="positive">Opportunity</Badge>
                <Badge variant="info">Evidence-backed</Badge>
                <Badge variant="warning">Monitor risk</Badge>
                <Badge variant="neutral">Insufficient evidence</Badge>
              </div>
            </div>
          </Card>

          <Card
            title="Research"
            description="Global search patterns will eventually connect to the intelligence API."
          >
            <div className="space-y-4">
              <Input
                id="company-search"
                label="Company or ticker"
                placeholder="Search companies"
              />

              <Input
                id="market-search"
                label="Market or sector"
                placeholder="Search sectors"
              />

              <Button fullWidth>Run analysis</Button>
            </div>
          </Card>
        </section>
      </div>
    </AppShell>
  );
}
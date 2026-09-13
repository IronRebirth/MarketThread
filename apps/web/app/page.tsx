import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { ThemeSwitcher } from "../components/ui/theme-switcher";

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
    <main className="min-h-screen bg-background">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-6 py-10 sm:px-8 lg:px-10">
        <header className="flex flex-col gap-6 border-b border-border pb-8">
          <div className="flex items-start justify-between gap-6">
            <div className="flex flex-col gap-3">
              <Badge variant="info">Design system</Badge>

              <div>
                <p className="text-sm font-medium text-brand">MarketThread</p>

                <h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
                  Global market intelligence, built for evidence-driven
                  decisions.
                </h1>

                <p className="mt-3 max-w-2xl text-base leading-7 text-text-secondary">
                  A restrained interface foundation for market research, event
                  intelligence, company analysis, and risk-aware insights.
                </p>
              </div>
            </div>

            <ThemeSwitcher />
          </div>

          <div className="flex flex-wrap gap-3">
            <Button>Primary action</Button>
            <Button variant="secondary">Secondary action</Button>
            <Button variant="ghost">Ghost action</Button>
            <Button variant="danger">Danger action</Button>
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
            title="Evidence summary"
            description="Example research content using the core information hierarchy."
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
                  The event may affect supply, demand, sentiment, and company
                  fundamentals, but available evidence remains incomplete.
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
            title="Research filter"
            description="Input styling for future search and analysis workflows."
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

        <section className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <p className="text-sm font-medium text-text-muted">Neutral</p>
            <div className="mt-3">
              <Badge variant="neutral">Watch</Badge>
            </div>
          </Card>

          <Card>
            <p className="text-sm font-medium text-text-muted">Positive</p>
            <div className="mt-3">
              <Badge variant="positive">Consider</Badge>
            </div>
          </Card>

          <Card>
            <p className="text-sm font-medium text-text-muted">Warning</p>
            <div className="mt-3">
              <Badge variant="warning">Moderate risk</Badge>
            </div>
          </Card>

          <Card>
            <p className="text-sm font-medium text-text-muted">Negative</p>
            <div className="mt-3">
              <Badge variant="negative">Reduce</Badge>
            </div>
          </Card>
        </section>
      </div>
    </main>
  );
}
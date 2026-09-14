import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

const horizonMetrics = [
  {
    horizon: "1D",
    evaluations: 84,
    accuracy: "68.4%",
    forwardReturn: "+1.82%",
    relativeReturn: "+0.74%",
    quality: "Reliable",
    qualityVariant: "positive" as const,
  },
  {
    horizon: "5D",
    evaluations: 78,
    accuracy: "64.1%",
    forwardReturn: "+3.46%",
    relativeReturn: "+1.38%",
    quality: "Reliable",
    qualityVariant: "positive" as const,
  },
  {
    horizon: "20D",
    evaluations: 61,
    accuracy: "59.0%",
    forwardReturn: "+6.27%",
    relativeReturn: "+2.14%",
    quality: "Reliable",
    qualityVariant: "positive" as const,
  },
];

const signalStrength = [
  {
    state: "Strong",
    evaluations: 34,
    accuracy: "73.5%",
    relativeReturn: "+2.41%",
  },
  {
    state: "Moderate",
    evaluations: 29,
    accuracy: "65.5%",
    relativeReturn: "+1.52%",
  },
  {
    state: "Weak",
    evaluations: 18,
    accuracy: "55.6%",
    relativeReturn: "+0.48%",
  },
  {
    state: "Insufficient",
    evaluations: 3,
    accuracy: "—",
    relativeReturn: "—",
  },
];

const recommendationStates = [
  {
    state: "Consider",
    evaluations: 31,
    accuracy: "71.0%",
    relativeReturn: "+2.08%",
  },
  {
    state: "Watch",
    evaluations: 21,
    accuracy: "66.7%",
    relativeReturn: "+1.31%",
  },
  {
    state: "Hold",
    evaluations: 17,
    accuracy: "58.8%",
    relativeReturn: "+0.82%",
  },
  {
    state: "Reduce",
    evaluations: 11,
    accuracy: "63.6%",
    relativeReturn: "+1.12%",
  },
  {
    state: "Insufficient Evidence",
    evaluations: 4,
    accuracy: "—",
    relativeReturn: "—",
  },
];

function MetricValue({
  value,
  label,
}: {
  value: string;
  label: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold tracking-tight text-text-primary">
        {value}
      </p>
    </div>
  );
}

function QualityIndicator({
  state,
  variant,
}: {
  state: string;
  variant: "positive" | "warning" | "neutral";
}) {
  return <Badge variant={variant}>{state}</Badge>;
}

export function BacktestDashboard() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Backtesting</Badge>
          <Badge variant="neutral">Read-only analysis</Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Backtest performance
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Evaluate historical signal performance across time horizons,
              recommendation states, signal strength, and evidence quality.
            </p>
          </div>

          <Button variant="secondary" disabled>
            Run new backtest
          </Button>
        </div>
      </header>

      <Card
        title="Current analysis"
        description="The workspace is ready for API-backed executions. A selected historical run will populate these metrics."
      >
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
          <MetricValue label="Evaluations" value="84" />
          <MetricValue label="Directional accuracy" value="68.4%" />
          <MetricValue label="Average return" value="+3.91%" />
          <MetricValue label="Relative return" value="+1.42%" />
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-5">
          <QualityIndicator state="Reliable" variant="positive" />
          <span className="text-sm text-text-secondary">
            84 valid evaluations
          </span>
          <span className="text-text-muted">•</span>
          <span className="text-sm text-text-secondary">
            Quality threshold satisfied
          </span>
        </div>
      </Card>

      <section className="grid gap-6 xl:grid-cols-[1.45fr_0.55fr]">
        <Card
          title="Performance by horizon"
          description="Forward and relative performance from horizon-specific evaluations."
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-[0.08em] text-text-muted">
                  <th className="px-2 py-3 font-medium">Horizon</th>
                  <th className="px-2 py-3 font-medium">Evaluations</th>
                  <th className="px-2 py-3 font-medium">Accuracy</th>
                  <th className="px-2 py-3 font-medium">Forward return</th>
                  <th className="px-2 py-3 font-medium">Relative return</th>
                  <th className="px-2 py-3 font-medium">Quality</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border">
                {horizonMetrics.map((metric) => (
                  <tr key={metric.horizon}>
                    <td className="px-2 py-4">
                      <span className="font-semibold text-text-primary">
                        {metric.horizon}
                      </span>
                    </td>
                    <td className="px-2 py-4 text-sm text-text-secondary">
                      {metric.evaluations}
                    </td>
                    <td className="px-2 py-4 text-sm font-medium text-text-primary">
                      {metric.accuracy}
                    </td>
                    <td className="px-2 py-4 text-sm font-medium text-positive">
                      {metric.forwardReturn}
                    </td>
                    <td className="px-2 py-4 text-sm font-medium text-positive">
                      {metric.relativeReturn}
                    </td>
                    <td className="px-2 py-4">
                      <QualityIndicator
                        state={metric.quality}
                        variant={metric.qualityVariant}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card
          title="Evidence quality"
          description="Quality is separate from performance and reflects how much evidence supports the result."
        >
          <div className="flex flex-col gap-5">
            <div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-sm text-text-secondary">
                  Evaluation coverage
                </span>
                <span className="text-sm font-semibold text-text-primary">
                  84 / 96
                </span>
              </div>

              <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full bg-brand"
                  style={{ width: "87.5%" }}
                />
              </div>

              <p className="mt-2 text-xs text-text-muted">87.5% coverage</p>
            </div>

            <div className="rounded-md border border-border bg-surface-subtle p-4">
              <p className="text-sm font-semibold text-text-primary">
                Reliable evidence
              </p>

              <p className="mt-1 text-sm leading-6 text-text-secondary">
                The current run exceeds the minimum sample requirement and
                provides sufficient evaluation coverage.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">Minimum sample</span>
                <span className="font-medium text-text-primary">30</span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">Current sample</span>
                <span className="font-medium text-text-primary">84</span>
              </div>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Card
          title="By signal strength"
          description="Compare outcomes across strength levels without treating confidence as profit probability."
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-[0.08em] text-text-muted">
                  <th className="px-2 py-3 font-medium">Strength</th>
                  <th className="px-2 py-3 font-medium">Evaluations</th>
                  <th className="px-2 py-3 font-medium">Accuracy</th>
                  <th className="px-2 py-3 font-medium">Relative return</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border">
                {signalStrength.map((item) => (
                  <tr key={item.state}>
                    <td className="px-2 py-4 text-sm font-medium text-text-primary">
                      {item.state}
                    </td>
                    <td className="px-2 py-4 text-sm text-text-secondary">
                      {item.evaluations}
                    </td>
                    <td className="px-2 py-4 text-sm text-text-primary">
                      {item.accuracy}
                    </td>
                    <td className="px-2 py-4 text-sm font-medium text-positive">
                      {item.relativeReturn}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card
          title="By recommendation state"
          description="Historical outcomes grouped by the recommendation state generated by MarketThread."
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-[0.08em] text-text-muted">
                  <th className="px-2 py-3 font-medium">State</th>
                  <th className="px-2 py-3 font-medium">Evaluations</th>
                  <th className="px-2 py-3 font-medium">Accuracy</th>
                  <th className="px-2 py-3 font-medium">Relative return</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border">
                {recommendationStates.map((item) => (
                  <tr key={item.state}>
                    <td className="px-2 py-4 text-sm font-medium text-text-primary">
                      {item.state}
                    </td>
                    <td className="px-2 py-4 text-sm text-text-secondary">
                      {item.evaluations}
                    </td>
                    <td className="px-2 py-4 text-sm text-text-primary">
                      {item.accuracy}
                    </td>
                    <td className="px-2 py-4 text-sm font-medium text-positive">
                      {item.relativeReturn}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      <Card
        title="Interpretation"
        description="How MarketThread should treat the displayed results."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-md border border-border bg-surface-subtle p-4">
            <p className="text-sm font-semibold text-text-primary">
              Performance
            </p>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Describes historical observed outcomes. It does not establish
              future returns or causality.
            </p>
          </div>

          <div className="rounded-md border border-border bg-surface-subtle p-4">
            <p className="text-sm font-semibold text-text-primary">
              Confidence
            </p>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Represents evidence support for a signal, not the probability
              that an investment will be profitable.
            </p>
          </div>

          <div className="rounded-md border border-border bg-surface-subtle p-4">
            <p className="text-sm font-semibold text-text-primary">
              Quality
            </p>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Indicates whether the amount and coverage of evidence are strong
              enough to support interpretation.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

import type {
  CompanyImpactDirection,
  ImpactType,
  MarketImpact,
  TimeHorizon,
} from "../../lib/market-impacts-api";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function getDirectionVariant(direction: CompanyImpactDirection) {
  if (direction === "positive") {
    return "positive" as const;
  }

  if (direction === "negative") {
    return "warning" as const;
  }

  if (direction === "uncertain") {
    return "neutral" as const;
  }

  return "info" as const;
}

function getImpactTypeVariant(impactType: ImpactType) {
  return impactType === "direct" ? ("info" as const) : ("neutral" as const);
}

function getHorizonVariant(timeHorizon: TimeHorizon) {
  if (timeHorizon === "short_term") {
    return "info" as const;
  }

  if (timeHorizon === "long_term") {
    return "neutral" as const;
  }

  if (timeHorizon === "uncertain") {
    return "warning" as const;
  }

  return "positive" as const;
}

export function MarketImpactCard({
  impact,
}: {
  impact: MarketImpact;
}) {
  return (
    <Card>
      <article className="flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={getImpactTypeVariant(impact.impact_type)}>
              {formatLabel(impact.impact_type)} exposure
            </Badge>

            <Badge variant={getDirectionVariant(impact.direction)}>
              {formatLabel(impact.direction)}
            </Badge>

            <Badge variant="info">
              {formatLabel(impact.factor)}
            </Badge>

            <Badge variant={getHorizonVariant(impact.time_horizon)}>
              {formatLabel(impact.time_horizon)}
            </Badge>
          </div>

          <div>
            <h2 className="text-xl font-semibold leading-7 tracking-tight text-text-primary">
              {impact.company_name}
            </h2>

            <p className="mt-2 break-all text-xs text-text-muted">
              Event {impact.event_id}
            </p>
          </div>

          <p className="text-sm leading-6 text-text-secondary">
            {impact.rationale}
          </p>
        </div>

        <div className="grid gap-5 border-t border-border pt-5 sm:grid-cols-2 xl:grid-cols-4">
          <ImpactMetric
            label="Evidence confidence"
            value={formatPercentage(impact.confidence)}
            description="Support for the structured market-impact classification."
          />

          <ImpactMetric
            label="Economic factor"
            value={formatLabel(impact.factor)}
            description="Primary economic transmission channel."
          />

          <ImpactMetric
            label="Time horizon"
            value={formatLabel(impact.time_horizon)}
            description="Expected period over which the impact may develop."
          />

          <ImpactMetric
            label="Evidence articles"
            value={String(impact.evidence_article_ids.length)}
            description="Source article identifiers retained for traceability."
          />
        </div>

        <div className="grid gap-5 xl:grid-cols-3">
          <ReferenceBlock
            label="Event ID"
            value={impact.event_id}
          />

          <ReferenceBlock
            label="Company Impact ID"
            value={impact.company_impact_id}
          />

          <ReferenceBlock
            label="Market Impact ID"
            value={impact.impact_id}
          />
        </div>

        <ImpactList
          title="Evidence article IDs"
          items={impact.evidence_article_ids}
          emptyMessage="No source article identifiers were recorded."
        />

        <div className="rounded-md border border-border bg-surface-subtle p-4">
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Interpretation
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            This assessment describes a possible economic transmission path
            from a detected event through a company exposure. The factor and
            horizon are structured interpretations, while confidence measures
            evidence support rather than the probability of a future market
            return.
          </p>
        </div>
      </article>
    </Card>
  );
}

function ImpactMetric({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <p className="mt-1 break-words text-sm font-semibold text-text-primary">
        {value}
      </p>

      <p className="mt-1 text-xs leading-5 text-text-muted">
        {description}
      </p>
    </div>
  );
}

function ReferenceBlock({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle p-4">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <p className="mt-2 break-all text-xs leading-5 text-text-secondary">
        {value}
      </p>
    </div>
  );
}

function ImpactList({
  title,
  items,
  emptyMessage,
}: {
  title: string;
  items: string[];
  emptyMessage: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {title}
      </p>

      {items.length > 0 ? (
        <div className="mt-3 flex flex-col gap-2">
          {items.map((item) => (
            <span
              key={item}
              className="break-all rounded-md border border-border bg-surface-subtle px-3 py-2 text-xs text-text-secondary"
            >
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-text-secondary">
          {emptyMessage}
        </p>
      )}
    </div>
  );
}

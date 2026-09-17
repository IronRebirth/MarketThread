import type {
  CompanyImpact,
  CompanyImpactDirection,
  ImpactType,
} from "../../lib/company-impacts-api";
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

export function CompanyImpactCard({
  impact,
}: {
  impact: CompanyImpact;
}) {
  return (
    <Card>
      <article className="flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={getImpactTypeVariant(impact.impact_type)}>
              {formatLabel(impact.impact_type)} impact
            </Badge>

            <Badge variant={getDirectionVariant(impact.direction)}>
              {formatLabel(impact.direction)}
            </Badge>

            {impact.ticker && (
              <Badge variant="neutral">{impact.ticker}</Badge>
            )}
          </div>

          <div>
            <h2 className="text-xl font-semibold leading-7 tracking-tight text-text-primary">
              {impact.company_name}
            </h2>

            {impact.ticker && (
              <p className="mt-1 text-sm font-medium text-text-secondary">
                {impact.ticker}
              </p>
            )}

            <p className="mt-2 break-all text-xs text-text-muted">
              Event {impact.event_id}
            </p>
          </div>

          <p className="text-sm leading-6 text-text-secondary">
            {impact.mechanism}
          </p>
        </div>

        <div className="grid gap-5 border-t border-border pt-5 sm:grid-cols-2 xl:grid-cols-4">
          <ImpactMetric
            label="Evidence confidence"
            value={formatPercentage(impact.confidence)}
            description="Support for the company-impact classification."
          />

          <ImpactMetric
            label="Impact type"
            value={formatLabel(impact.impact_type)}
            description="How the company is associated with the event."
          />

          <ImpactMetric
            label="Direction"
            value={formatLabel(impact.direction)}
            description="Classified directional implication."
          />

          <ImpactMetric
            label="Evidence articles"
            value={String(impact.evidence_article_ids.length)}
            description="Source article identifiers retained for traceability."
          />
        </div>

        <div className="grid gap-5 xl:grid-cols-2">
          <CompanyImpactList
            title="Evidence article IDs"
            items={impact.evidence_article_ids}
            emptyMessage="No source article identifiers were recorded."
            breakWords
          />

          <CompanyImpactList
            title="Event reference"
            items={[impact.event_id]}
            emptyMessage="No event reference was recorded."
            breakWords
          />
        </div>

        <div className="border-t border-border pt-5">
          <p className="text-sm font-semibold text-text-primary">
            Impact rationale
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {impact.rationale}
          </p>
        </div>

        <div className="rounded-md border border-border bg-surface-subtle p-4">
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
            Interpretation
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            This record describes how the company is structurally exposed to a
            detected market event. Confidence measures support for the
            classification; it is not a probability of future returns or a
            guarantee of market performance.
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

function CompanyImpactList({
  title,
  items,
  emptyMessage,
  breakWords = false,
}: {
  title: string;
  items: string[];
  emptyMessage: string;
  breakWords?: boolean;
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
              className={`rounded-md border border-border bg-surface-subtle px-3 py-2 text-xs text-text-secondary ${
                breakWords ? "break-all" : ""
              }`}
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

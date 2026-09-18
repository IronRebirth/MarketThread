import type { MarketSignal } from "../../lib/signals-api";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function getDirectionVariant(direction: MarketSignal["direction"]) {
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

function getOpportunityVariant(
  opportunity: MarketSignal["opportunity"],
) {
  if (opportunity === "opportunity") {
    return "positive" as const;
  }

  if (opportunity === "reduce") {
    return "warning" as const;
  }

  if (opportunity === "insufficient_evidence") {
    return "neutral" as const;
  }

  return "info" as const;
}

function getStrengthVariant(strength: MarketSignal["strength"]) {
  if (strength === "strong") {
    return "positive" as const;
  }

  if (strength === "moderate") {
    return "info" as const;
  }

  if (strength === "weak") {
    return "warning" as const;
  }

  return "neutral" as const;
}

function formatTimestamp(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function SignalCard({ signal }: { signal: MarketSignal }) {
  return (
    <Card>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={getOpportunityVariant(signal.opportunity)}>
                {formatLabel(signal.opportunity)}
              </Badge>

              <Badge variant={getDirectionVariant(signal.direction)}>
                {formatLabel(signal.direction)}
              </Badge>

              <Badge variant={getStrengthVariant(signal.strength)}>
                {formatLabel(signal.strength)} evidence
              </Badge>
            </div>

            <div className="mt-3">
              <h2 className="text-xl font-semibold tracking-tight text-text-primary">
                {signal.company_name}
              </h2>

              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-secondary">
                {signal.ticker && <span>{signal.ticker}</span>}

                <span>
                  Horizon: {formatLabel(signal.time_horizon)}
                </span>

                <span>
                  Created {formatTimestamp(signal.created_at)}
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-5 lg:min-w-64">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                Confidence
              </p>

              <p className="mt-1 text-xl font-semibold text-text-primary">
                {formatPercentage(signal.confidence)}
              </p>

              <p className="mt-1 text-xs leading-5 text-text-secondary">
                Evidence support
              </p>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                Risk
              </p>

              <p className="mt-1 text-xl font-semibold text-text-primary">
                {formatPercentage(signal.risk_score)}
              </p>

              <p className="mt-1 text-xs leading-5 text-text-secondary">
                Risk score
              </p>
            </div>
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <p className="text-sm font-semibold text-text-primary">
            Why this signal exists
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {signal.rationale}
          </p>
        </div>

        <div className="grid gap-5 xl:grid-cols-3">
          <SignalList
            title="Supporting factors"
            items={signal.supporting_factors}
            emptyMessage="No supporting factors were recorded."
          />

          <SignalList
            title="Contradicting factors"
            items={signal.contradicting_factors}
            emptyMessage="No contradicting factors were recorded."
          />

          <SignalList
            title="Invalidation conditions"
            items={signal.invalidation_conditions}
            emptyMessage="No invalidation conditions were recorded."
          />
        </div>

        <div className="grid gap-4 border-t border-border pt-5 sm:grid-cols-2 lg:grid-cols-3">
          <SignalMetadata
            label="Evidence references"
            value={String(signal.evidence_article_ids.length)}
          />

          <SignalMetadata
            label="Event"
            value={signal.event_id}
            monospace
          />

          <SignalMetadata
            label="Market impact"
            value={signal.market_impact_id ?? "Not linked"}
            monospace={signal.market_impact_id !== null}
          />
        </div>
      </div>
    </Card>
  );
}

function SignalList({
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
            <div
              key={item}
              className="rounded-md border border-border bg-surface-subtle px-3 py-2 text-sm leading-6 text-text-secondary"
            >
              {item}
            </div>
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

function SignalMetadata({
  label,
  value,
  monospace = false,
}: {
  label: string;
  value: string;
  monospace?: boolean;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
        {label}
      </p>

      <p
        className={`mt-1 break-all text-sm font-medium text-text-primary ${
          monospace ? "font-mono text-xs" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}

import type { Recommendation } from "../../lib/recommendations-api";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";
import { RecommendationProvenancePanel } from "./recommendation-provenance-panel";

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function getStateVariant(state: Recommendation["state"]) {
  if (state === "consider") {
    return "positive" as const;
  }

  if (state === "reduce") {
    return "warning" as const;
  }

  if (state === "insufficient_evidence") {
    return "neutral" as const;
  }

  return "info" as const;
}

function getDirectionVariant(direction: string) {
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

export function RecommendationCard({
  recommendation,
}: {
  recommendation: Recommendation;
}) {
  return (
    <Card>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={getStateVariant(recommendation.state)}>
                {formatLabel(recommendation.state)}
              </Badge>

              <Badge
                variant={getDirectionVariant(
                  recommendation.signal_direction,
                )}
              >
                {formatLabel(recommendation.signal_direction)}
              </Badge>
            </div>

            <div className="mt-3">
              <h2 className="text-xl font-semibold tracking-tight text-text-primary">
                {recommendation.company_name}
              </h2>

              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-secondary">
                {recommendation.ticker && (
                  <span className="font-mono">
                    {recommendation.ticker}
                  </span>
                )}

                <span>
                  Horizon: {formatLabel(recommendation.time_horizon)}
                </span>

                <span>
                  Created {formatTimestamp(recommendation.created_at)}
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-5 lg:min-w-64">
            <RecommendationMetric
              label="Confidence"
              value={formatPercentage(recommendation.confidence_score)}
              description={formatLabel(recommendation.confidence_level)}
            />

            <RecommendationMetric
              label="Risk"
              value={formatPercentage(recommendation.risk_score)}
              description={formatLabel(recommendation.risk_level)}
            />
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <p className="text-sm font-semibold text-text-primary">
            Recommendation rationale
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {recommendation.rationale}
          </p>
        </div>

        <div className="grid gap-5 xl:grid-cols-3">
          <RecommendationList
            title="Supporting factors"
            items={recommendation.supporting_factors}
            emptyMessage="No supporting factors were recorded."
          />

          <RecommendationList
            title="Contradicting factors"
            items={recommendation.contradicting_factors}
            emptyMessage="No contradicting factors were recorded."
          />

          <RecommendationList
            title="Assumptions"
            items={recommendation.assumptions}
            emptyMessage="No assumptions were recorded."
          />
        </div>

        <RecommendationList
          title="Invalidation conditions"
          items={recommendation.invalidation_conditions}
          emptyMessage="No invalidation conditions were recorded."
        />

        <div className="grid gap-4 border-t border-border pt-5 sm:grid-cols-2 lg:grid-cols-4">
          <RecommendationMetadata
            label="Evidence references"
            value={String(recommendation.evidence_article_ids.length)}
          />

          <RecommendationMetadata
            label="Signal"
            value={recommendation.signal_id}
            monospace
          />

          <RecommendationMetadata
            label="Event"
            value={recommendation.event_id}
            monospace
          />

          <RecommendationMetadata
            label="Recommendation"
            value={recommendation.recommendation_id}
            monospace
          />
        </div>

        <RecommendationProvenancePanel
          recommendationId={recommendation.recommendation_id}
        />
      </div>
    </Card>
  );
}

function RecommendationMetric({
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

      <p className="mt-1 text-xl font-semibold text-text-primary">
        {value}
      </p>

      <p className="mt-1 text-xs leading-5 text-text-secondary">
        {description}
      </p>
    </div>
  );
}

function RecommendationList({
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
          {items.map((item, index) => (
            <div
              key={`${item}-${index}`}
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

function RecommendationMetadata({
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

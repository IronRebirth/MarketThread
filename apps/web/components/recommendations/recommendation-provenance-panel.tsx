"use client";

import { useState } from "react";

import {
  fetchRecommendationProvenance,
  RecommendationsApiError,
  type RecommendationProvenance,
} from "../../lib/recommendations-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

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

function getErrorMessage(error: unknown) {
  if (error instanceof RecommendationsApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Recommendation provenance could not be loaded.";
}

export function RecommendationProvenancePanel({
  recommendationId,
}: {
  recommendationId: string;
}) {
  const [provenance, setProvenance] =
    useState<RecommendationProvenance | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleToggle = async () => {
    if (isExpanded) {
      setIsExpanded(false);
      return;
    }

    setIsExpanded(true);

    if (provenance !== null) {
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextProvenance = await fetchRecommendationProvenance(
        recommendationId,
      );

      setProvenance(nextProvenance);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="border-t border-border pt-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-text-primary">
            Evidence provenance
          </p>

          <p className="mt-1 text-sm leading-6 text-text-secondary">
            Inspect the persisted inputs and assumptions behind this
            recommendation.
          </p>
        </div>

        <Button
          variant="secondary"
          onClick={() => void handleToggle()}
          disabled={isLoading}
        >
          {isLoading
            ? "Loading provenance"
            : isExpanded
              ? "Hide provenance"
              : "View provenance"}
        </Button>
      </div>

      {isExpanded && (
        <div className="mt-4">
          {errorMessage ? (
            <div className="rounded-md border border-negative-soft bg-negative-soft px-4 py-3">
              <p className="text-sm leading-6 text-negative">
                {errorMessage}
              </p>

              <div className="mt-3">
                <Button
                  variant="secondary"
                  onClick={() => {
                    setProvenance(null);
                    void handleToggle();
                  }}
                >
                  Retry
                </Button>
              </div>
            </div>
          ) : isLoading ? (
            <div className="h-48 animate-pulse rounded-md bg-surface-muted" />
          ) : provenance !== null ? (
            <ProvenanceContent provenance={provenance} />
          ) : null}
        </div>
      )}
    </div>
  );
}

function ProvenanceContent({
  provenance,
}: {
  provenance: RecommendationProvenance;
}) {
  return (
    <div className="flex flex-col gap-5 rounded-md border border-border bg-surface-subtle p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="info">
          Ruleset {provenance.ruleset_version}
        </Badge>

        <Badge variant="neutral">
          Created {formatTimestamp(provenance.created_at)}
        </Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <ProvenanceMetadata
          label="Recommendation"
          value={provenance.recommendation_id}
          monospace
        />

        <ProvenanceMetadata
          label="Signal"
          value={provenance.signal_id}
          monospace
        />

        <ProvenanceMetadata
          label="Market impact"
          value={provenance.market_impact_id}
          monospace
        />

        <ProvenanceMetadata
          label="Event"
          value={provenance.event_id}
          monospace
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <ProvenanceList
          title="Input identifiers"
          items={provenance.input_ids}
          emptyMessage="No input identifiers were recorded."
          monospace
        />

        <ProvenanceList
          title="Evidence article identifiers"
          items={provenance.evidence_article_ids}
          emptyMessage="No evidence article identifiers were recorded."
          monospace
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <ProvenanceList
          title="Assumptions"
          items={provenance.assumptions}
          emptyMessage="No assumptions were recorded."
        />

        <ProvenanceList
          title="Invalidation conditions"
          items={provenance.invalidation_conditions}
          emptyMessage="No invalidation conditions were recorded."
        />
      </div>
    </div>
  );
}

function ProvenanceList({
  title,
  items,
  emptyMessage,
  monospace = false,
}: {
  title: string;
  items: string[];
  emptyMessage: string;
  monospace?: boolean;
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
              className={`break-all rounded-md border border-border bg-surface px-3 py-2 text-sm leading-6 text-text-secondary ${
                monospace ? "font-mono text-xs" : ""
              }`}
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

function ProvenanceMetadata({
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

import type {
  MarketEvent,
  MarketRelevance,
  ImpactDirection,
} from "../../lib/events-api";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
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

function getRelevanceVariant(relevance: MarketRelevance) {
  if (relevance === "high") {
    return "positive" as const;
  }

  if (relevance === "medium") {
    return "info" as const;
  }

  return "neutral" as const;
}

function getImpactVariant(direction: ImpactDirection) {
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

export function EventCard({ event }: { event: MarketEvent }) {
  return (
    <Card>
      <article className="flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">
              {formatLabel(event.event_type)}
            </Badge>

            <Badge variant="neutral">
              {formatLabel(event.catalyst)}
            </Badge>

            <Badge variant={getRelevanceVariant(event.market_relevance)}>
              {formatLabel(event.market_relevance)} market relevance
            </Badge>

            <Badge variant={getImpactVariant(event.impact_direction)}>
              {formatLabel(event.impact_direction)} impact
            </Badge>
          </div>

          <div>
            <h2 className="text-xl font-semibold leading-7 tracking-tight text-text-primary">
              {event.title}
            </h2>

            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-secondary">
              <span>First seen {formatTimestamp(event.first_seen_at)}</span>
              <span>Last seen {formatTimestamp(event.last_seen_at)}</span>
            </div>
          </div>

          <p className="text-sm leading-6 text-text-secondary">
            {event.summary}
          </p>
        </div>

        <div className="grid gap-5 border-t border-border pt-5 sm:grid-cols-2 xl:grid-cols-4">
          <EventMetric
            label="Evidence confidence"
            value={formatPercentage(event.confidence)}
            description="Support for the detected event classification."
          />

          <EventMetric
            label="Event type"
            value={formatLabel(event.event_type)}
            description="Structured event classification."
          />

          <EventMetric
            label="Entities"
            value={
              event.affected_entities.length > 0
                ? event.affected_entities.join(", ")
                : "None recorded"
            }
            description="Entities associated with the event."
          />

          <EventMetric
            label="Sectors"
            value={
              event.affected_sectors.length > 0
                ? event.affected_sectors.join(", ")
                : "None recorded"
            }
            description="Potentially affected market sectors."
          />
        </div>

        <div className="grid gap-5 xl:grid-cols-3">
          <EventList
            title="Affected entities"
            items={event.affected_entities}
            emptyMessage="No entities were recorded."
          />

          <EventList
            title="Affected sectors"
            items={event.affected_sectors}
            emptyMessage="No sectors were recorded."
          />

          <EventList
            title="Source articles"
            items={event.source_article_ids}
            emptyMessage="No source article identifiers were recorded."
            breakWords
          />
        </div>

        <div className="border-t border-border pt-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-text-primary">
                Event interpretation
              </p>

              <p className="mt-1 text-sm leading-6 text-text-secondary">
                The detected event is a structured interpretation of source
                news. Confidence describes evidence support for the
                classification and does not represent the probability of a
                future market outcome.
              </p>
            </div>

            <div className="shrink-0 rounded-md border border-border bg-surface-subtle px-3 py-2">
              <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
                Event ID
              </p>

              <p className="mt-1 break-all text-xs text-text-secondary">
                {event.event_id}
              </p>
            </div>
          </div>
        </div>
      </article>
    </Card>
  );
}

function EventMetric({
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

function EventList({
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
        <div className="mt-3 flex flex-wrap gap-2">
          {items.map((item) => (
            <span
              key={item}
              className={`rounded-md border border-border bg-surface-subtle px-3 py-1.5 text-sm text-text-secondary ${
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

import type {
  ImpactDirection,
  MarketRelevance,
  NewsFeedItem,
  Sentiment,
} from "../../lib/news-api";
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

function getSentimentVariant(sentiment: Sentiment) {
  if (sentiment === "positive") {
    return "positive" as const;
  }

  if (sentiment === "negative") {
    return "warning" as const;
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

export function NewsCard({ item }: { item: NewsFeedItem }) {
  const { article, intelligence } = item;

  return (
    <Card>
      <article className="flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={getRelevanceVariant(intelligence.market_relevance)}>
              {formatLabel(intelligence.market_relevance)} market relevance
            </Badge>

            <Badge variant={getSentimentVariant(intelligence.sentiment)}>
              {formatLabel(intelligence.sentiment)}
            </Badge>

            <Badge variant={getImpactVariant(intelligence.impact_direction)}>
              {formatLabel(intelligence.impact_direction)} impact
            </Badge>
          </div>

          <div>
            <h2 className="text-xl font-semibold leading-7 tracking-tight text-text-primary">
              <a
                href={article.url}
                target="_blank"
                rel="noreferrer"
                className="underline decoration-brand/20 underline-offset-4 hover:decoration-brand"
              >
                {article.title}
              </a>
            </h2>

            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-secondary">
              <span className="font-medium">{article.source_name}</span>

              <span>{article.source_domain}</span>

              <span>Published {formatTimestamp(article.published_at)}</span>
            </div>
          </div>

          {article.summary && (
            <p className="text-sm leading-6 text-text-secondary">
              {article.summary}
            </p>
          )}
        </div>

        <div className="grid gap-5 border-t border-border pt-5 sm:grid-cols-2 xl:grid-cols-4">
          <NewsMetric
            label="Confidence"
            value={formatPercentage(intelligence.confidence)}
            description="Evidence support for the classification."
          />

          <NewsMetric
            label="Catalyst"
            value={
              intelligence.catalyst
                ? formatLabel(intelligence.catalyst)
                : "Unspecified"
            }
            description="Detected market-moving catalyst."
          />

          <NewsMetric
            label="Entities"
            value={
              intelligence.entities.length > 0
                ? intelligence.entities.join(", ")
                : "None recorded"
            }
            description="Entities identified in the article."
          />

          <NewsMetric
            label="Sectors"
            value={
              intelligence.affected_sectors.length > 0
                ? intelligence.affected_sectors.join(", ")
                : "None recorded"
            }
            description="Potentially affected sectors."
          />
        </div>

        <div className="grid gap-5 xl:grid-cols-3">
          <NewsList
            title="Topics"
            items={intelligence.topics}
            emptyMessage="No topics were extracted."
          />

          <NewsList
            title="Entities"
            items={intelligence.entities}
            emptyMessage="No entities were extracted."
          />

          <NewsList
            title="Affected sectors"
            items={intelligence.affected_sectors}
            emptyMessage="No sectors were identified."
          />
        </div>

        <div className="border-t border-border pt-5">
          <p className="text-sm font-semibold text-text-primary">
            Intelligence rationale
          </p>

          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {intelligence.rationale}
          </p>
        </div>

        {article.author && (
          <div className="border-t border-border pt-5">
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              Author
            </p>

            <p className="mt-1 text-sm text-text-secondary">
              {article.author}
            </p>
          </div>
        )}
      </article>
    </Card>
  );
}

function NewsMetric({
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

function NewsList({
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
        <div className="mt-3 flex flex-wrap gap-2">
          {items.map((item) => (
            <span
              key={item}
              className="rounded-md border border-border bg-surface-subtle px-3 py-1.5 text-sm text-text-secondary"
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

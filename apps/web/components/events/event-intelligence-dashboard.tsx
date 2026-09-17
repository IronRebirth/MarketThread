"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  EventCatalyst,
  EventFilters,
  EventType,
  EventsApiError,
  fetchMarketEvents,
  ImpactDirection,
  MarketEvent,
  MarketRelevance,
} from "../../lib/events-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { EventCard } from "./event-card";

const EVENT_PAGE_SIZE = 100;

const DEFAULT_FILTERS: EventFilters = {
  limit: EVENT_PAGE_SIZE,
};

function localDateToIso(value: string, endOfDay = false) {
  if (!value) {
    return undefined;
  }

  return new Date(
    `${value}T${endOfDay ? "23:59:59.999" : "00:00:00.000"}`,
  ).toISOString();
}

function formatPercentage(value: number | null) {
  if (value === null) {
    return "—";
  }

  return `${(value * 100).toFixed(0)}%`;
}

function formatOptionLabel(value: string) {
  return value.replaceAll("_", " ");
}

export function EventIntelligenceDashboard() {
  const [events, setEvents] = useState<MarketEvent[]>([]);
  const [eventType, setEventType] = useState<EventType | "">("");
  const [catalyst, setCatalyst] = useState<EventCatalyst | "">("");
  const [marketRelevance, setMarketRelevance] = useState<
    MarketRelevance | ""
  >("");
  const [impactDirection, setImpactDirection] = useState<
    ImpactDirection | ""
  >("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [appliedFilters, setAppliedFilters] =
    useState<EventFilters>(DEFAULT_FILTERS);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(
    null,
  );

  const loadEvents = useCallback(async (filters: EventFilters) => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextEvents = await fetchMarketEvents({
        ...filters,
        limit: EVENT_PAGE_SIZE,
      });

      setEvents(nextEvents);
    } catch (error) {
      setEvents([]);

      setErrorMessage(
        error instanceof EventsApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "The event intelligence feed could not be loaded.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadEvents(DEFAULT_FILTERS);
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadEvents]);

  const metrics = useMemo(() => {
    if (events.length === 0) {
      return {
        eventCount: 0,
        highRelevanceCount: 0,
        uncertainDirectionCount: 0,
        averageConfidence: null,
      };
    }

    const highRelevanceCount = events.filter(
      (event) => event.market_relevance === "high",
    ).length;

    const uncertainDirectionCount = events.filter(
      (event) => event.impact_direction === "uncertain",
    ).length;

    const averageConfidence =
      events.reduce((total, event) => total + event.confidence, 0) /
      events.length;

    return {
      eventCount: events.length,
      highRelevanceCount,
      uncertainDirectionCount,
      averageConfidence,
    };
  }, [events]);

  const buildFilters = (): EventFilters => ({
    eventType: eventType || undefined,
    catalyst: catalyst || undefined,
    marketRelevance: marketRelevance || undefined,
    impactDirection: impactDirection || undefined,
    startAt: localDateToIso(startDate),
    endAt: localDateToIso(endDate, true),
    limit: EVENT_PAGE_SIZE,
  });

  const validateDateRange = () => {
    if (startDate && endDate && startDate > endDate) {
      setActionErrorMessage(
        "The start date must be earlier than or equal to the end date.",
      );
      return false;
    }

    return true;
  };

  const handleApplyFilters = () => {
    setActionErrorMessage(null);

    if (!validateDateRange()) {
      return;
    }

    const nextFilters = buildFilters();

    setAppliedFilters(nextFilters);
    void loadEvents(nextFilters);
  };

  const handleClearFilters = () => {
    setEventType("");
    setCatalyst("");
    setMarketRelevance("");
    setImpactDirection("");
    setStartDate("");
    setEndDate("");
    setActionErrorMessage(null);
    setAppliedFilters(DEFAULT_FILTERS);

    void loadEvents(DEFAULT_FILTERS);
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Event Intelligence</Badge>
          <Badge variant="positive">API connected</Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Event intelligence
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Explore persisted market events detected from normalized news
              and inspect their classifications, catalysts, evidence, and
              provenance.
            </p>
          </div>

          <div>
            <Button
              variant="secondary"
              onClick={() => void loadEvents(appliedFilters)}
              disabled={isLoading}
            >
              {isLoading ? "Loading events" : "Refresh events"}
            </Button>
          </div>
        </div>
      </header>

      {errorMessage && (
        <Card
          title="Event feed unavailable"
          description="The persisted event workspace could not retrieve events from the MarketThread API."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button onClick={() => void loadEvents(appliedFilters)}>
                Try again
              </Button>
            </div>
          </div>
        </Card>
      )}

      <Card
        title="Event filters"
        description="These controls map directly to the persisted event filters exposed by the MarketThread API."
      >
        <div className="flex flex-col gap-5">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <SelectField
              id="event-type"
              label="Event type"
              value={eventType}
              onChange={(value) => setEventType(value as EventType | "")}
              options={[
                "monetary_policy",
                "inflation",
                "trade_policy",
                "geopolitical",
                "corporate_action",
                "earnings",
                "regulation",
                "macroeconomic",
                "other",
              ]}
            />

            <SelectField
              id="event-catalyst"
              label="Catalyst"
              value={catalyst}
              onChange={(value) => setCatalyst(value as EventCatalyst | "")}
              options={[
                "rate_cut",
                "rate_hike",
                "inflation_surprise",
                "tariff",
                "sanction",
                "military_escalation",
                "merger",
                "acquisition",
                "earnings_surprise",
                "regulatory_change",
                "other",
              ]}
            />

            <SelectField
              id="market-relevance"
              label="Market relevance"
              value={marketRelevance}
              onChange={(value) =>
                setMarketRelevance(value as MarketRelevance | "")
              }
              options={["low", "medium", "high"]}
            />

            <SelectField
              id="impact-direction"
              label="Impact direction"
              value={impactDirection}
              onChange={(value) =>
                setImpactDirection(value as ImpactDirection | "")
              }
              options={["positive", "neutral", "negative", "uncertain"]}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <DateField
              id="event-start-date"
              label="From"
              value={startDate}
              onChange={setStartDate}
            />

            <DateField
              id="event-end-date"
              label="Through"
              value={endDate}
              onChange={setEndDate}
            />
          </div>

          {actionErrorMessage && (
            <div
              role="alert"
              className="rounded-md border border-border bg-warning-soft px-3 py-2.5 text-sm leading-6 text-warning"
            >
              {actionErrorMessage}
            </div>
          )}

          <div className="flex flex-wrap gap-2 border-t border-border pt-4">
            <Button
              onClick={handleApplyFilters}
              disabled={isLoading}
            >
              Apply filters
            </Button>

            <Button
              variant="secondary"
              onClick={handleClearFilters}
              disabled={isLoading}
            >
              Clear
            </Button>
          </div>
        </div>
      </Card>

      {!isLoading && !errorMessage && (
        <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <MetricValue
            label="Events"
            value={String(metrics.eventCount)}
            description="Persisted events returned by the current view."
          />

          <MetricValue
            label="High relevance"
            value={String(metrics.highRelevanceCount)}
            description="Events classified with high market relevance."
          />

          <MetricValue
            label="Uncertain direction"
            value={String(metrics.uncertainDirectionCount)}
            description="Events where the evidence does not support a directional classification."
          />

          <MetricValue
            label="Average confidence"
            value={formatPercentage(metrics.averageConfidence)}
            description="Average evidence confidence across loaded events."
          />
        </section>
      )}

      {!isLoading && !errorMessage && events.length === 0 ? (
        <Card
          title="No persisted events"
          description="The event workspace is connected to PostgreSQL, but no events match the current filters."
        >
          <div className="flex min-h-56 items-center justify-center rounded-md border border-border bg-surface-subtle px-6 text-center">
            <div className="max-w-xl">
              <p className="text-sm font-medium text-text-primary">
                No market events match the current view.
              </p>

              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Clear the filters or ensure that persisted news articles have
                been processed through the Event Intelligence API. Empty
                results are kept explicit rather than substituting example or
                mock market events.
              </p>
            </div>
          </div>
        </Card>
      ) : !isLoading && !errorMessage ? (
        <section className="flex flex-col gap-5">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-text-primary">
              Detected market events
            </h2>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Events are ordered by first-seen time in the persistence layer.
              Each record retains its structured classification and source
              article identifiers for traceability.
            </p>
          </div>

          <div className="flex flex-col gap-5">
            {events.map((event) => (
              <EventCard
                key={event.event_id}
                event={event}
              />
            ))}
          </div>
        </section>
      ) : (
        <Card
          title="Loading event intelligence"
          description="Retrieving persisted event classifications and provenance."
        >
          <div className="flex flex-col gap-4">
            {[1, 2, 3].map((item) => (
              <div
                key={item}
                className="h-72 animate-pulse rounded-md bg-surface-muted"
              />
            ))}
          </div>
        </Card>
      )}

      {!isLoading && !errorMessage && (
        <Card
          title="Interpretation"
          description="How MarketThread should treat detected event intelligence."
        >
          <div className="grid gap-4 md:grid-cols-3">
            <Interpretation
              title="Event classification"
              description="Identifies the structured event type and catalyst detected from the underlying news evidence."
            />

            <Interpretation
              title="Market implication"
              description="Describes the classified relevance and directional implication without presenting it as a guaranteed market result."
            />

            <Interpretation
              title="Evidence confidence"
              description="Measures support for the classification. It is separate from investment opportunity, future return probability, and risk."
            />
          </div>
        </Card>
      )}
    </div>
  );
}

function SelectField({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-sm font-medium text-text-primary">{label}</span>

      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-border bg-background px-3 py-2.5 text-sm capitalize text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
      >
        <option value="">All</option>

        {options.map((option) => (
          <option key={option} value={option}>
            {formatOptionLabel(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

function DateField({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-sm font-medium text-text-primary">{label}</span>

      <input
        id={id}
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-border bg-background px-3 py-2.5 text-sm text-text-primary outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
      />
    </label>
  );
}

function MetricValue({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <Card>
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
          {label}
        </p>

        <p className="mt-2 text-2xl font-semibold tracking-tight text-text-primary">
          {value}
        </p>

        <p className="mt-2 text-xs leading-5 text-text-muted">
          {description}
        </p>
      </div>
    </Card>
  );
}

function Interpretation({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle p-4">
      <p className="text-sm font-semibold text-text-primary">{title}</p>

      <p className="mt-2 text-sm leading-6 text-text-secondary">
        {description}
      </p>
    </div>
  );
}

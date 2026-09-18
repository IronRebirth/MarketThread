"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CompanyImpactDirection,
  ImpactFactor,
  ImpactType,
  MarketImpact,
  MarketImpactFilters,
  MarketImpactsApiError,
  fetchMarketImpacts,
  TimeHorizon,
} from "../../lib/market-impacts-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { MarketImpactCard } from "./market-impact-card";

const MARKET_IMPACT_PAGE_SIZE = 100;

const DEFAULT_FILTERS: MarketImpactFilters = {
  limit: MARKET_IMPACT_PAGE_SIZE,
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

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

export function MarketImpactDashboard() {
  const [impacts, setImpacts] = useState<MarketImpact[]>([]);
  const [companyName, setCompanyName] = useState("");
  const [eventId, setEventId] = useState("");
  const [impactType, setImpactType] = useState<ImpactType | "">("");
  const [direction, setDirection] = useState<
    CompanyImpactDirection | ""
  >("");
  const [factor, setFactor] = useState<ImpactFactor | "">("");
  const [timeHorizon, setTimeHorizon] = useState<TimeHorizon | "">("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [appliedFilters, setAppliedFilters] =
    useState<MarketImpactFilters>(DEFAULT_FILTERS);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(
    null,
  );

  const loadImpacts = useCallback(
    async (filters: MarketImpactFilters) => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const nextImpacts = await fetchMarketImpacts({
          ...filters,
          limit: MARKET_IMPACT_PAGE_SIZE,
        });

        setImpacts(nextImpacts);
      } catch (error) {
        setImpacts([]);

        setErrorMessage(
          error instanceof MarketImpactsApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "The market impact workspace could not be loaded.",
        );
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadImpacts(DEFAULT_FILTERS);
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadImpacts]);

  const metrics = useMemo(() => {
    if (impacts.length === 0) {
      return {
        impactCount: 0,
        companyCount: 0,
        mediumOrLongTermCount: 0,
        averageConfidence: null,
      };
    }

    const companyCount = new Set(
      impacts.map((impact) => impact.company_name),
    ).size;

    const mediumOrLongTermCount = impacts.filter(
      (impact) =>
        impact.time_horizon === "medium_term" ||
        impact.time_horizon === "long_term",
    ).length;

    const averageConfidence =
      impacts.reduce((total, impact) => total + impact.confidence, 0) /
      impacts.length;

    return {
      impactCount: impacts.length,
      companyCount,
      mediumOrLongTermCount,
      averageConfidence,
    };
  }, [impacts]);

  const buildFilters = (): MarketImpactFilters => ({
    companyName: companyName.trim() || undefined,
    eventId: eventId.trim() || undefined,
    impactType: impactType || undefined,
    direction: direction || undefined,
    factor: factor || undefined,
    timeHorizon: timeHorizon || undefined,
    startAt: localDateToIso(startDate),
    endAt: localDateToIso(endDate, true),
    limit: MARKET_IMPACT_PAGE_SIZE,
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
    void loadImpacts(nextFilters);
  };

  const handleClearFilters = () => {
    setCompanyName("");
    setEventId("");
    setImpactType("");
    setDirection("");
    setFactor("");
    setTimeHorizon("");
    setStartDate("");
    setEndDate("");
    setActionErrorMessage(null);
    setAppliedFilters(DEFAULT_FILTERS);

    void loadImpacts(DEFAULT_FILTERS);
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Market Impact</Badge>
          <Badge variant="positive">API connected</Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Market impact
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Explore the economic transmission paths connecting detected
              market events to company-level exposures, including factor,
              horizon, direction, evidence, and confidence.
            </p>
          </div>

          <div>
            <Button
              variant="secondary"
              onClick={() => void loadImpacts(appliedFilters)}
              disabled={isLoading}
            >
              {isLoading ? "Loading impacts" : "Refresh impacts"}
            </Button>
          </div>
        </div>
      </header>

      {errorMessage && (
        <Card
          title="Market impact unavailable"
          description="The persisted market-impact workspace could not retrieve records from the MarketThread API."
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-6 text-text-secondary">
              {errorMessage}
            </p>

            <div>
              <Button onClick={() => void loadImpacts(appliedFilters)}>
                Try again
              </Button>
            </div>
          </div>
        </Card>
      )}

      <Card
        title="Market impact filters"
        description="These filters map directly to the persisted market-impact API."
      >
        <div className="flex flex-col gap-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <Input
              id="market-impact-company"
              label="Company"
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
              placeholder="Exact company name"
            />

            <Input
              id="market-impact-event-id"
              label="Event ID"
              value={eventId}
              onChange={(event) => setEventId(event.target.value)}
              placeholder="UUID of a persisted event"
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <SelectField
              id="market-impact-type"
              label="Impact type"
              value={impactType}
              onChange={(value) => setImpactType(value as ImpactType | "")}
              options={["direct", "indirect"]}
            />

            <SelectField
              id="market-impact-direction"
              label="Direction"
              value={direction}
              onChange={(value) =>
                setDirection(value as CompanyImpactDirection | "")
              }
              options={["positive", "neutral", "negative", "uncertain"]}
            />

            <SelectField
              id="market-impact-factor"
              label="Economic factor"
              value={factor}
              onChange={(value) => setFactor(value as ImpactFactor | "")}
              options={[
                "demand",
                "revenue",
                "input_costs",
                "financing",
                "valuation",
                "supply_chain",
                "market_access",
                "regulatory_burden",
                "competitive_position",
                "operating_risk",
                "investor_sentiment",
                "other",
              ]}
            />

            <SelectField
              id="market-impact-horizon"
              label="Time horizon"
              value={timeHorizon}
              onChange={(value) =>
                setTimeHorizon(value as TimeHorizon | "")
              }
              options={[
                "short_term",
                "medium_term",
                "long_term",
                "uncertain",
              ]}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <DateField
              id="market-impact-start-date"
              label="From"
              value={startDate}
              onChange={setStartDate}
            />

            <DateField
              id="market-impact-end-date"
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
            label="Impacts"
            value={String(metrics.impactCount)}
            description="Persisted market-impact records in the current view."
          />

          <MetricValue
            label="Companies"
            value={String(metrics.companyCount)}
            description="Distinct companies represented by the current view."
          />

          <MetricValue
            label="Medium / long term"
            value={String(metrics.mediumOrLongTermCount)}
            description="Impacts classified with medium- or long-term horizons."
          />

          <MetricValue
            label="Average confidence"
            value={formatPercentage(metrics.averageConfidence)}
            description="Average evidence confidence across loaded impacts."
          />
        </section>
      )}

      {!isLoading && !errorMessage && impacts.length === 0 ? (
        <Card
          title="No persisted market impacts"
          description="The market-impact workspace is connected to PostgreSQL, but no records match the current filters."
        >
          <div className="flex min-h-56 items-center justify-center rounded-md border border-border bg-surface-subtle px-6 text-center">
            <div className="max-w-xl">
              <p className="text-sm font-medium text-text-primary">
                No market impacts match the current view.
              </p>

              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Clear the filters or process a persisted event with existing
                company-impact records through the Market Impact API. Empty
                results remain explicit rather than being replaced by sample
                data.
              </p>
            </div>
          </div>
        </Card>
      ) : !isLoading && !errorMessage ? (
        <section className="flex flex-col gap-5">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-text-primary">
              Economic market impacts
            </h2>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Each assessment represents a structured transmission path from
              an event through a company exposure. The records retain their
              event and evidence references for traceability.
            </p>
          </div>

          <div className="flex flex-col gap-5">
            {impacts.map((impact) => (
              <MarketImpactCard
                key={impact.impact_id}
                impact={impact}
              />
            ))}
          </div>
        </section>
      ) : (
        <Card
          title="Loading market impact"
          description="Retrieving persisted economic transmission assessments."
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
          description="How MarketThread should treat market-impact intelligence."
        >
          <div className="grid gap-4 md:grid-cols-3">
            <Interpretation
              title="Economic factor"
              description="Identifies the primary channel through which the event may transmit to the company, such as financing, market access, demand, or regulatory burden."
            />

            <Interpretation
              title="Time horizon"
              description="Provides the structured horizon associated with the impact assessment. An uncertain horizon remains explicitly uncertain."
            />

            <Interpretation
              title="Confidence"
              description="Measures evidence support for the assessment and remains distinct from probability of profit, opportunity, or investment outcome."
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
            {formatLabel(option)}
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

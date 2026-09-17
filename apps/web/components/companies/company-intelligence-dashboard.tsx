"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CompanyImpact,
  CompanyImpactDirection,
  CompanyImpactFilters,
  CompanyImpactsApiError,
  fetchCompanyImpacts,
  ImpactType,
} from "../../lib/company-impacts-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { CompanyImpactCard } from "./company-impact-card";

const COMPANY_IMPACT_PAGE_SIZE = 100;

const DEFAULT_FILTERS: CompanyImpactFilters = {
  limit: COMPANY_IMPACT_PAGE_SIZE,
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

export function CompanyIntelligenceDashboard() {
  const [impacts, setImpacts] = useState<CompanyImpact[]>([]);
  const [companyName, setCompanyName] = useState("");
  const [ticker, setTicker] = useState("");
  const [eventId, setEventId] = useState("");
  const [impactType, setImpactType] = useState<ImpactType | "">("");
  const [direction, setDirection] = useState<
    CompanyImpactDirection | ""
  >("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [appliedFilters, setAppliedFilters] =
    useState<CompanyImpactFilters>(DEFAULT_FILTERS);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(
    null,
  );

  const loadImpacts = useCallback(
    async (filters: CompanyImpactFilters) => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const nextImpacts = await fetchCompanyImpacts({
          ...filters,
          limit: COMPANY_IMPACT_PAGE_SIZE,
        });

        setImpacts(nextImpacts);
      } catch (error) {
        setImpacts([]);

        setErrorMessage(
          error instanceof CompanyImpactsApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "The company intelligence workspace could not be loaded.",
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
        negativeCount: 0,
        averageConfidence: null,
      };
    }

    const companyCount = new Set(
      impacts.map((impact) => impact.company_name),
    ).size;

    const negativeCount = impacts.filter(
      (impact) => impact.direction === "negative",
    ).length;

    const averageConfidence =
      impacts.reduce((total, impact) => total + impact.confidence, 0) /
      impacts.length;

    return {
      impactCount: impacts.length,
      companyCount,
      negativeCount,
      averageConfidence,
    };
  }, [impacts]);

  const buildFilters = (): CompanyImpactFilters => ({
    companyName: companyName.trim() || undefined,
    ticker: ticker.trim() || undefined,
    eventId: eventId.trim() || undefined,
    impactType: impactType || undefined,
    direction: direction || undefined,
    startAt: localDateToIso(startDate),
    endAt: localDateToIso(endDate, true),
    limit: COMPANY_IMPACT_PAGE_SIZE,
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
    setTicker("");
    setEventId("");
    setImpactType("");
    setDirection("");
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
          <Badge variant="info">Company Intelligence</Badge>
          <Badge variant="positive">API connected</Badge>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Company intelligence
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Explore how detected market events are associated with companies,
              including directional impact, transmission mechanism, evidence,
              and classification confidence.
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
          title="Company intelligence unavailable"
          description="The persisted company-impact workspace could not retrieve records from the MarketThread API."
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
        title="Company impact filters"
        description="These controls map to the persisted company-impact filters exposed by the MarketThread API."
      >
        <div className="flex flex-col gap-5">
          <div className="grid gap-4 lg:grid-cols-3">
            <Input
              id="company-name"
              label="Company"
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
              placeholder="Exact company name"
            />

            <Input
              id="company-ticker"
              label="Ticker"
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
              placeholder="Ticker symbol"
            />

            <Input
              id="company-event-id"
              label="Event ID"
              value={eventId}
              onChange={(event) => setEventId(event.target.value)}
              placeholder="UUID of a persisted event"
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <SelectField
              id="company-impact-type"
              label="Impact type"
              value={impactType}
              onChange={(value) => setImpactType(value as ImpactType | "")}
              options={["direct", "indirect"]}
            />

            <SelectField
              id="company-impact-direction"
              label="Direction"
              value={direction}
              onChange={(value) =>
                setDirection(value as CompanyImpactDirection | "")
              }
              options={["positive", "neutral", "negative", "uncertain"]}
            />

            <DateField
              id="company-start-date"
              label="From"
              value={startDate}
              onChange={setStartDate}
            />

            <DateField
              id="company-end-date"
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
            description="Persisted company-impact records in the current view."
          />

          <MetricValue
            label="Companies"
            value={String(metrics.companyCount)}
            description="Distinct companies represented by the current view."
          />

          <MetricValue
            label="Negative direction"
            value={String(metrics.negativeCount)}
            description="Company impacts classified with a negative direction."
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
          title="No persisted company impacts"
          description="The company workspace is connected to PostgreSQL, but no company-impact records match the current filters."
        >
          <div className="flex min-h-56 items-center justify-center rounded-md border border-border bg-surface-subtle px-6 text-center">
            <div className="max-w-xl">
              <p className="text-sm font-medium text-text-primary">
                No company impacts match the current view.
              </p>

              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Clear the filters or process a persisted market event through
                the Company Impact API. Empty results remain explicit rather
                than being replaced by example companies.
              </p>
            </div>
          </div>
        </Card>
      ) : !isLoading && !errorMessage ? (
        <section className="flex flex-col gap-5">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-text-primary">
              Company impact assessments
            </h2>

            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Company impacts are derived from persisted market events. Each
              assessment retains its event reference and source article IDs for
              traceability.
            </p>
          </div>

          <div className="flex flex-col gap-5">
            {impacts.map((impact) => (
              <CompanyImpactCard
                key={impact.impact_id}
                impact={impact}
              />
            ))}
          </div>
        </section>
      ) : (
        <Card
          title="Loading company intelligence"
          description="Retrieving persisted company-impact classifications and evidence."
        >
          <div className="flex flex-col gap-4">
            {[1, 2, 3].map((item) => (
              <div
                key={item}
                className="h-64 animate-pulse rounded-md bg-surface-muted"
              />
            ))}
          </div>
        </Card>
      )}

      {!isLoading && !errorMessage && (
        <Card
          title="Interpretation"
          description="How MarketThread should treat company-impact intelligence."
        >
          <div className="grid gap-4 md:grid-cols-3">
            <Interpretation
              title="Company exposure"
              description="Describes the detected relationship between a market event and a company, rather than asserting a guaranteed business or market outcome."
            />

            <Interpretation
              title="Transmission mechanism"
              description="Explains the economic channel through which the event may affect the company, such as financing conditions, market access, supply-chain costs, or regulation."
            />

            <Interpretation
              title="Evidence confidence"
              description="Measures support for the structured classification. It remains separate from opportunity, expected return, and investment risk."
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

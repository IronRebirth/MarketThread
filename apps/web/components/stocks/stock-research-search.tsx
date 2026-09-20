"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";

export function StockResearchSearch() {
  const router = useRouter();
  const [symbol, setSymbol] = useState("");

  const openResearch = () => {
    const normalizedSymbol = symbol.trim().toUpperCase();

    if (!normalizedSymbol) {
      return;
    }

    router.push(`/stocks/${encodeURIComponent(normalizedSymbol)}`);
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Stock Research</Badge>
          <Badge variant="positive">Evidence driven</Badge>
        </div>

        <div>
          <p className="text-sm font-medium text-brand">MarketThread</p>

          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            Research a stock
          </h1>

          <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
            Explore persisted price history, technical indicators, company
            impact, market events, signals, recommendations, confidence, risk,
            and evidence for one instrument.
          </p>
        </div>
      </header>

      <Card
        title="Stock symbol"
        description="Enter an instrument symbol that exists in the MarketThread market-data layer."
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1">
            <Input
              id="stock-research-symbol"
              label="Ticker"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  openResearch();
                }
              }}
              placeholder="e.g. NVDA"
              autoComplete="off"
            />
          </div>

          <Button
            onClick={openResearch}
            disabled={!symbol.trim()}
          >
            Open research
          </Button>
        </div>
      </Card>

      <Card
        title="Research posture"
        description="How this page handles missing information."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <ResearchNote
            title="Persisted first"
            description="The page reads the existing database-backed market, event, impact, signal, and recommendation APIs rather than using placeholder data."
          />

          <ResearchNote
            title="Transparent gaps"
            description="A missing quote, incomplete history, or unavailable fundamentals is shown as unavailable instead of being substituted with a fabricated value."
          />

          <ResearchNote
            title="No guaranteed outcome"
            description="Signals, confidence, risk, and historical indicators are presented as research context rather than a promise of future investment performance."
          />
        </div>
      </Card>
    </div>
  );
}

function ResearchNote({
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

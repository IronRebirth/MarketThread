"use client";

import { useState } from "react";

import {
  fetchInstrument,
  MarketDataApiError,
  type Instrument,
} from "../../lib/market-data-api";
import {
  PortfolioApiError,
  upsertPortfolioPosition,
} from "../../lib/portfolio-api";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";

interface PortfolioPositionFormProps {
  portfolioId: string;
  onPositionSaved: () => Promise<void>;
}

function getErrorMessage(error: unknown, fallback: string) {
  if (
    error instanceof PortfolioApiError ||
    error instanceof MarketDataApiError
  ) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export function PortfolioPositionForm({
  portfolioId,
  onPositionSaved,
}: PortfolioPositionFormProps) {
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [averageCost, setAverageCost] = useState("");

  const [instrument, setInstrument] = useState<Instrument | null>(
    null,
  );
  const [isResolving, setIsResolving] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(
    null,
  );

  const handleResolve = async () => {
    const normalizedTicker = ticker.trim().toUpperCase();

    if (!normalizedTicker) {
      setErrorMessage("Enter a ticker symbol.");
      setInstrument(null);
      return;
    }

    setIsResolving(true);
    setErrorMessage(null);
    setInstrument(null);

    try {
      const resolvedInstrument =
        await fetchInstrument(normalizedTicker);

      if (!resolvedInstrument.is_active) {
        setErrorMessage(
          "This instrument is currently inactive and cannot be added.",
        );
        return;
      }

      setInstrument(resolvedInstrument);
    } catch (error) {
      setErrorMessage(
        getErrorMessage(
          error,
          "The instrument could not be resolved.",
        ),
      );
    } finally {
      setIsResolving(false);
    }
  };

  const handleSave = async () => {
    if (!instrument) {
      setErrorMessage("Resolve an active instrument first.");
      return;
    }

    const normalizedQuantity = quantity.trim();
    const normalizedAverageCost = averageCost.trim();

    if (!normalizedQuantity || Number(normalizedQuantity) <= 0) {
      setErrorMessage("Quantity must be greater than zero.");
      return;
    }

    if (
      !normalizedAverageCost ||
      Number(normalizedAverageCost) < 0
    ) {
      setErrorMessage("Average cost must be zero or greater.");
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);

    try {
      await upsertPortfolioPosition(
        portfolioId,
        instrument.id,
        normalizedQuantity,
        normalizedAverageCost,
      );

      setTicker("");
      setQuantity("");
      setAverageCost("");
      setInstrument(null);

      await onPositionSaved();
    } catch (error) {
      setErrorMessage(
        getErrorMessage(
          error,
          "The portfolio position could not be saved.",
        ),
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card
      title="Add or update a position"
      description="Resolve a persisted active instrument, then enter its current quantity and average cost."
    >
      <div className="flex flex-col gap-5">
        {errorMessage && (
          <div
            role="alert"
            className="rounded-md border border-negative bg-negative-soft px-4 py-3"
          >
            <p className="text-sm leading-6 text-negative">
              {errorMessage}
            </p>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[1.2fr_auto] lg:items-end">
          <Input
            label="Ticker symbol"
            value={ticker}
            onChange={(event) => {
              setTicker(event.target.value);
              setInstrument(null);
              setErrorMessage(null);
            }}
            placeholder="e.g. NVDA"
            autoCapitalize="characters"
            autoComplete="off"
            maxLength={32}
            disabled={isResolving || isSaving}
          />

          <Button
            variant="secondary"
            onClick={() => void handleResolve()}
            disabled={
              isResolving ||
              isSaving ||
              !ticker.trim()
            }
          >
            {isResolving ? "Resolving" : "Resolve instrument"}
          </Button>
        </div>

        {instrument && (
          <div className="rounded-md border border-border bg-surface-subtle px-4 py-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="font-mono text-sm font-semibold text-text-primary">
                  {instrument.symbol}
                </p>

                <p className="mt-1 text-sm text-text-secondary">
                  {instrument.name}
                </p>
              </div>

              <div className="text-left text-xs text-text-muted sm:text-right">
                <p>{instrument.exchange}</p>
                <p className="mt-1">
                  {instrument.asset_class} · {instrument.currency}
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Quantity"
            type="number"
            value={quantity}
            onChange={(event) => {
              setQuantity(event.target.value);
              setErrorMessage(null);
            }}
            placeholder="e.g. 25"
            min="0"
            step="any"
            inputMode="decimal"
            disabled={!instrument || isSaving}
          />

          <Input
            label="Average cost"
            type="number"
            value={averageCost}
            onChange={(event) => {
              setAverageCost(event.target.value);
              setErrorMessage(null);
            }}
            placeholder="e.g. 110.50"
            min="0"
            step="any"
            inputMode="decimal"
            disabled={!instrument || isSaving}
          />
        </div>

        <div>
          <Button
            onClick={() => void handleSave()}
            disabled={
              !instrument ||
              isSaving ||
              !quantity.trim() ||
              !averageCost.trim()
            }
          >
            {isSaving ? "Saving position" : "Save position"}
          </Button>
        </div>

        <p className="text-xs leading-5 text-text-muted">
          Saving an existing instrument replaces its current persisted
          quantity and average cost instead of creating a duplicate
          position.
        </p>
      </div>
    </Card>
  );
}

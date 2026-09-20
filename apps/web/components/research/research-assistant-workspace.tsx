"use client";

import { FormEvent, useMemo, useState } from "react";

import { useAuth } from "../auth/auth-provider";
import { AuthRequiredPrompt } from "../auth/auth-required-prompt";
import {
  askResearchAssistant,
  ResearchAssistantApiError,
  type ResearchAnswer,
} from "../../lib/research-api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";

const EXAMPLE_QUESTIONS = [
  "What recent events are affecting NVDA?",
  "What evidence supports the latest signal for AAPL?",
  "What risks are currently visible in my portfolio?",
];

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDateTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(date);
}

export function ResearchAssistantWorkspace() {
  const { user, isLoading: isAuthLoading } = useAuth();
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState("");
  const [answer, setAnswer] = useState<ResearchAnswer | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const asOfIso = useMemo(() => {
    if (!asOf) {
      return undefined;
    }

    const date = new Date(asOf);

    if (Number.isNaN(date.getTime())) {
      return undefined;
    }

    return date.toISOString();
  }, [asOf]);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!question.trim() || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      setAnswer(await askResearchAssistant(question, asOfIso));
    } catch (error) {
      setAnswer(null);

      if (error instanceof ResearchAssistantApiError) {
        setErrorMessage(error.message);
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("The research assistant could not answer this question.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isAuthLoading) {
    return (
      <div className="flex flex-col gap-5">
        <Card
          title="Loading research assistant"
          description="Checking your MarketThread session."
        >
          <div className="h-24 animate-pulse rounded-md bg-surface-muted" />
        </Card>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col gap-8">
        <header className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">Research Assistant</Badge>
            <Badge variant="positive">Grounded</Badge>
          </div>

          <div>
            <p className="text-sm font-medium text-brand">MarketThread</p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Ask MarketThread
            </h1>

            <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
              Ask questions across persisted market evidence, events, company
              impacts, signals, recommendations, fundamentals, and your
              portfolio context.
            </p>
          </div>
        </header>

        <AuthRequiredPrompt nextPath="/research" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info">Research Assistant</Badge>
          <Badge variant={answer?.grounded === false ? "warning" : "positive"}>
            Grounded
          </Badge>
        </div>

        <div>
          <p className="text-sm font-medium text-brand">MarketThread</p>

          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            Ask MarketThread
          </h1>

          <p className="mt-3 max-w-3xl text-base leading-7 text-text-secondary">
            Ask a research question and receive a source-linked synthesis of
            the persisted MarketThread evidence available at a specific point
            in time.
          </p>
        </div>
      </header>

      <Card
        title="Research question"
        description="The assistant searches persisted MarketThread evidence before generating an answer."
      >
        <form className="flex flex-col gap-5" onSubmit={submitQuestion}>
          <div className="flex flex-col gap-2">
            <label
              htmlFor="research-question"
              className="text-sm font-medium text-text-primary"
            >
              Question
            </label>

            <textarea
              id="research-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about a company, event, signal, risk, or portfolio impact."
              rows={5}
              maxLength={2000}
              className="w-full rounded-md border border-border-strong bg-surface px-3 py-2 text-sm leading-6 text-text-primary placeholder:text-text-muted outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
              disabled={isSubmitting}
            />

            <p className="text-xs text-text-muted">
              {question.length}/2000
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
            <Input
              id="research-as-of"
              label="Historical cutoff (optional)"
              type="datetime-local"
              value={asOf}
              onChange={(event) => setAsOf(event.target.value)}
              disabled={isSubmitting}
            />

            <Button
              type="submit"
              disabled={!question.trim() || isSubmitting}
            >
              {isSubmitting ? "Researching..." : "Ask MarketThread"}
            </Button>
          </div>

          <div>
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-muted">
              Example questions
            </p>

            <div className="mt-3 flex flex-wrap gap-2">
              {EXAMPLE_QUESTIONS.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setQuestion(example)}
                  className="rounded-full border border-border bg-surface-subtle px-3 py-2 text-left text-xs text-text-secondary hover:border-brand hover:text-text-primary"
                  disabled={isSubmitting}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        </form>
      </Card>

      {errorMessage && (
        <Card
          title="Research request unavailable"
          description="The assistant did not return a usable grounded answer."
        >
          <p className="text-sm leading-6 text-text-secondary" role="alert">
            {errorMessage}
          </p>
        </Card>
      )}

      {isSubmitting && (
        <Card
          title="Building your research context"
          description="Retrieving persisted evidence and preparing the grounded answer."
        >
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((item) => (
              <div
                key={item}
                className="h-20 animate-pulse rounded-md bg-surface-muted"
              />
            ))}
          </div>
        </Card>
      )}

      {answer && !isSubmitting && (
        <ResearchAnswerCard answer={answer} />
      )}

      <Card
        title="Research posture"
        description="What this assistant will and will not do."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <ResearchNote
            title="Evidence first"
            description="The assistant receives a bounded MarketThread context assembled from persisted records before the model is asked to synthesize an answer."
          />

          <ResearchNote
            title="Citations are validated"
            description="The API only accepts citation identifiers that exist in the retrieved MarketThread source-reference set."
          />

          <ResearchNote
            title="Missing evidence stays missing"
            description="When the retrieved context is insufficient, the answer exposes limitations instead of filling gaps with unsupported market facts."
          />
        </div>
      </Card>
    </div>
  );
}

function ResearchAnswerCard({ answer }: { answer: ResearchAnswer }) {
  return (
    <div className="flex flex-col gap-5">
      <Card
        title="Research answer"
        description={`As of ${formatDateTime(
          answer.as_of,
        )} · generated ${formatDateTime(answer.generated_at)} · model ${answer.model}`}
      >
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="positive">Grounded answer</Badge>
            <Badge variant="info">
              {answer.citations.length} source
              {answer.citations.length === 1 ? "" : "s"}
            </Badge>
          </div>

          <div>
            <p className="text-base leading-8 text-text-primary whitespace-pre-line">
              {answer.answer}
            </p>
          </div>

          {answer.key_points.length > 0 && (
            <AnswerList
              title="Key points"
              items={answer.key_points}
            />
          )}

          <div className="rounded-md border border-border bg-surface-subtle p-4">
            <p className="text-sm font-semibold text-text-primary">
              Explanation
            </p>

            <p className="mt-2 text-sm leading-6 text-text-secondary whitespace-pre-line">
              {answer.explanation}
            </p>
          </div>

          {answer.uncertainty.length > 0 && (
            <AnswerList
              title="Uncertainty and limitations"
              items={answer.uncertainty}
            />
          )}
        </div>
      </Card>

      <Card
        title="Sources"
        description="These references were validated against the persisted MarketThread context."
      >
        {answer.citations.length === 0 ? (
          <p className="text-sm leading-6 text-text-muted">
            No source references were returned with this answer.
          </p>
        ) : (
          <div className="flex flex-col divide-y divide-border">
            {answer.citations.map((citation) => (
              <div key={citation.reference_id} className="py-4 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="neutral">
                    {formatLabel(citation.source_type)}
                  </Badge>

                  <span className="text-xs text-text-muted">
                    {formatDate(citation.observed_at)}
                  </span>
                </div>

                {citation.url ? (
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 block text-sm font-medium text-brand hover:underline"
                  >
                    {citation.title ?? citation.reference_id}
                  </a>
                ) : (
                  <p className="mt-2 text-sm font-medium text-text-primary">
                    {citation.title ?? citation.reference_id}
                  </p>
                )}

                <p className="mt-1 font-mono text-[11px] text-text-muted">
                  {citation.reference_id}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function AnswerList({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  return (
    <div>
      <p className="text-sm font-semibold text-text-primary">{title}</p>

      <div className="mt-3 flex flex-col gap-2">
        {items.map((item) => (
          <div
            key={item}
            className="border-l-2 border-border pl-3 text-sm leading-6 text-text-secondary"
          >
            {item}
          </div>
        ))}
      </div>
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

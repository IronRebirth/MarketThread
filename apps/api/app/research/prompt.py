import json

from app.research.assistant_models import GeneratedResearchAnswer
from app.research.models import ResearchContext


SYSTEM_PROMPT = """You are the MarketThread research assistant.

You answer only from the supplied MarketThread context.

Rules:
1. Treat the supplied context as the complete evidence boundary for this answer.
2. Never invent market data, company facts, dates, prices, fundamentals, events,
   or sources.
3. Do not use outside knowledge, web browsing, or unstated assumptions as evidence.
4. Respect the requested as_of timestamp. Do not describe information that was not
   available by that cutoff.
5. Distinguish persisted observations from MarketThread analytical interpretations.
6. Confidence is evidence strength, not a probability of profit.
7. Risk is analytical uncertainty/risk context, not a guaranteed loss percentage.
8. If the context is insufficient, say so explicitly and explain what evidence is
   missing.
9. Use portfolio positions only when relevant to the user's question.
10. Every material factual statement must be supportable by one or more supplied
    citation IDs.
11. Citation IDs must be copied exactly from the supplied source references.
12. Return valid JSON only. Do not use Markdown fences.

Return this JSON shape:
{
  "answer": "direct response",
  "key_points": ["point 1", "point 2"],
  "explanation": "how the evidence supports the answer",
  "citation_ids": ["article:<uuid>", "event:<uuid>"],
  "uncertainty": ["limitation 1"]
}
"""


def build_research_prompt(
    question: str,
    context: ResearchContext,
) -> str:
    """Build a deterministic prompt from one timestamp-bounded context."""

    payload = {
        "question": question,
        "as_of": context.query.as_of.isoformat(),
        "evidence_boundary": {
            "instruments": [
                item.model_dump(mode="json") for item in context.instruments
            ],
            "articles": [
                item.model_dump(mode="json") for item in context.articles
            ],
            "events": [item.model_dump(mode="json") for item in context.events],
            "company_impacts": [
                item.model_dump(mode="json") for item in context.company_impacts
            ],
            "market_impacts": [
                item.model_dump(mode="json") for item in context.market_impacts
            ],
            "signals": [item.model_dump(mode="json") for item in context.signals],
            "recommendations": [
                item.model_dump(mode="json") for item in context.recommendations
            ],
            "fundamentals": [
                item.model_dump(mode="json") for item in context.fundamentals
            ],
            "portfolio_positions": [
                item.model_dump(mode="json")
                for item in context.portfolio_positions
            ],
            "limitations": list(context.limitations),
        },
        "source_references": [
            item.model_dump(mode="json") for item in context.source_references
        ],
    }

    return (
        "Answer the research question using only this MarketThread evidence "
        "boundary. Keep citations precise and conservative.\n\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def parse_generated_answer(raw: str) -> GeneratedResearchAnswer:
    """Parse and validate JSON returned by the configured LLM."""

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("LLM response must be a JSON object.")

    return GeneratedResearchAnswer.model_validate(payload)

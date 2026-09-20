from datetime import UTC, datetime
from uuid import UUID

from app.core.config import get_settings
from app.research.assistant_models import (
    ResearchAnswer,
    ResearchAnswerRequest,
)
from app.research.llm import (
    LLMConfigurationError,
    LLMProvider,
    LLMResponseError,
    OpenAIResponsesProvider,
)
from app.research.models import ResearchSourceReference
from app.research.prompt import SYSTEM_PROMPT, build_research_prompt, parse_generated_answer
from app.research.retrieval import ResearchContextService


class ResearchAssistantService:
    """Generate grounded answers from a timestamp-bounded research context."""

    def __init__(
        self,
        session,
        provider: LLMProvider | None = None,
    ) -> None:
        self.session = session
        self.provider = provider or self._create_provider()

    @staticmethod
    def _create_provider() -> LLMProvider:
        settings = get_settings()

        if not settings.llm_api_key:
            raise LLMConfigurationError(
                "LLM_API_KEY is not configured.",
            )

        return OpenAIResponsesProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
        )

    async def answer(
        self,
        request: ResearchAnswerRequest,
        *,
        user_id: UUID,
    ) -> ResearchAnswer:
        as_of = request.as_of or datetime.now(UTC)

        if as_of.tzinfo is None:
            raise ValueError("as_of must include a timezone.")

        query = request.model_copy(
            update={
                "as_of": as_of,
            },
        )

        context = await ResearchContextService(self.session).build(
            query.model_copy(
                update={
                    "limit": request.limit,
                    "as_of": as_of,
                },
            ),
            user_id=user_id,
        )

        raw = await self.provider.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_research_prompt(
                request.question,
                context,
            ),
        )

        try:
            generated = parse_generated_answer(raw)
        except ValueError as exc:
            raise LLMResponseError(str(exc)) from exc

        references_by_id = {
            reference.reference_id: reference
            for reference in context.source_references
        }

        citations: list[ResearchSourceReference] = []

        for citation_id in generated.citation_ids:
            reference = references_by_id.get(citation_id)

            if reference is None:
                raise LLMResponseError(
                    f"LLM cited an unknown MarketThread reference: {citation_id}",
                )

            citations.append(reference)

        if context.source_references and not citations:
            raise LLMResponseError(
                "The LLM answer did not cite any MarketThread evidence.",
            )

        model_name = getattr(self.provider, "model", "configured-llm")

        return ResearchAnswer(
            question=request.question,
            as_of=as_of,
            answer=generated.answer,
            key_points=generated.key_points,
            explanation=generated.explanation,
            uncertainty=generated.uncertainty
            or context.limitations,
            citations=tuple(citations),
            model=model_name,
            generated_at=datetime.now(UTC),
            grounded=True,
        )

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.research.assistant_models import ResearchAnswerRequest
from app.research.llm import LLMResponseError
from app.research.models import (
    ResearchContext,
    ResearchQuery,
    ResearchSourceReference,
)
from app.research.prompt import parse_generated_answer
from app.research.service import ResearchAssistantService


class FakeLLMProvider:
    name = "fake"
    model = "fake-research-model"

    def __init__(self, response: str) -> None:
        self.response = response
        self.system_prompt = None
        self.user_prompt = None

    async def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.response


def make_context() -> ResearchContext:
    reference = ResearchSourceReference(
        reference_id=f"article:{uuid4()}",
        source_type="news_article",
        source_record_id=uuid4(),
        observed_at=datetime(2026, 9, 20, tzinfo=UTC),
        title="Test article",
        url="https://example.com/test",
    )

    return ResearchContext(
        query=ResearchQuery(
            question="What happened?",
            as_of=datetime(2026, 9, 20, tzinfo=UTC),
        ),
        retrieval_started_at=datetime(2026, 9, 20, tzinfo=UTC),
        instruments=(),
        articles=(),
        events=(),
        company_impacts=(),
        market_impacts=(),
        signals=(),
        recommendations=(),
        fundamentals=(),
        portfolio_positions=(),
        source_references=(reference,),
        limitations=(),
    )


def test_parse_generated_answer_requires_json_object() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_generated_answer("not-json")


@pytest.mark.asyncio
async def test_service_rejects_unknown_citation(monkeypatch) -> None:
    context = make_context()
    provider = FakeLLMProvider(
        '{"answer":"Evidence-based answer","key_points":[],"explanation":"context",'
        '"citation_ids":["article:unknown"],"uncertainty":[]}',
    )

    async def fake_build(self, query, *, user_id):
        return context

    monkeypatch.setattr(
        "app.research.service.ResearchContextService.build",
        fake_build,
    )

    with pytest.raises(
        LLMResponseError,
        match="unknown MarketThread reference",
    ):
        await ResearchAssistantService(
            session=None,
            provider=provider,
        ).answer(
            ResearchAnswerRequest(
                question="What happened?",
                as_of=datetime(2026, 9, 20, tzinfo=UTC),
            ),
            user_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_service_returns_validated_source_references(monkeypatch) -> None:
    context = make_context()
    provider = FakeLLMProvider(
        '{"answer":"Evidence-based answer","key_points":["Point"],'
        '"explanation":"Supported by the article.",'
        f'"citation_ids":["{context.source_references[0].reference_id}"],'
        '"uncertainty":[]}',
    )

    async def fake_build(self, query, *, user_id):
        return context

    monkeypatch.setattr(
        "app.research.service.ResearchContextService.build",
        fake_build,
    )

    result = await ResearchAssistantService(
        session=None,
        provider=provider,
    ).answer(
        ResearchAnswerRequest(
            question="What happened?",
            as_of=datetime(2026, 9, 20, tzinfo=UTC),
        ),
        user_id=uuid4(),
    )

    assert result.grounded is True
    assert result.model == "fake-research-model"
    assert len(result.citations) == 1
    assert result.citations[0].reference_id == context.source_references[0].reference_id
    assert provider.system_prompt is not None
    assert provider.user_prompt is not None
    assert context.source_references[0].reference_id in provider.user_prompt

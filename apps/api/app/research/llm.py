from typing import Protocol

import httpx


class LLMProviderError(RuntimeError):
    """Base error for LLM provider failures."""


class LLMConfigurationError(LLMProviderError):
    """Raised when the LLM provider is not configured."""


class LLMResponseError(LLMProviderError):
    """Raised when the LLM provider returns an unusable response."""


class LLMProvider(Protocol):
    """Provider abstraction used by the research assistant."""

    name: str
    model: str

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate one research answer from structured prompts."""


class OpenAIResponsesProvider:
    """OpenAI Responses API adapter using the existing httpx dependency."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        url = f"{self._base_url}/responses"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "instructions": system_prompt,
                        "input": user_prompt,
                    },
                )
        except httpx.HTTPError as exc:
            raise LLMResponseError(
                "The configured LLM provider could not be reached.",
            ) from exc

        if response.status_code in {401, 403}:
            raise LLMConfigurationError(
                "The configured LLM API key was rejected.",
            )

        if response.status_code >= 400:
            raise LLMResponseError(
                f"The LLM provider returned HTTP {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMResponseError(
                "The LLM provider returned invalid JSON.",
            ) from exc

        text = self._extract_text(payload)

        if not text:
            raise LLMResponseError(
                "The LLM provider returned no text output.",
            )

        return text

    @staticmethod
    def _extract_text(payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None

        output_text = payload.get("output_text")

        if isinstance(output_text, str):
            return output_text

        output = payload.get("output")

        if not isinstance(output, list):
            return None

        fragments: list[str] = []

        for item in output:
            if not isinstance(item, dict):
                continue

            content = item.get("content")

            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue

                text = block.get("text")

                if isinstance(text, str):
                    fragments.append(text)

        return "".join(fragments) or None

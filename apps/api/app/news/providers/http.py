from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx

from app.news.models import NewsArticle
from app.news.providers.errors import (
    NewsProviderError,
    NewsProviderInvalidResponseError,
    NewsProviderUnavailableError,
)


class HttpNewsProvider:
    """REST-based NewsAPI provider adapter."""

    name = "newsapi"

    _DEFAULT_LATEST_QUERY = "market OR stocks OR finance OR economy"

    def __init__(
        self,
        base_url: str = "https://newsapi.org",
        api_key: str | None = None,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = client

    def _headers(self) -> dict[str, str]:
        """Build authentication headers for the provider."""

        if not self.api_key:
            return {}

        return {"X-Api-Key": self.api_key}

    async def _get(
        self,
        path: str,
        params: Mapping[str, str],
    ) -> dict[str, object]:
        """Perform a provider request and validate the top-level response."""

        url = f"{self.base_url}/{path.lstrip('/')}"

        if self._client is not None:
            response = await self._client.get(
                url,
                params=params,
                headers=self._headers(),
            )
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.get(
                        url,
                        params=params,
                        headers=self._headers(),
                    )
                except httpx.HTTPError as exc:
                    raise NewsProviderUnavailableError(
                        "News provider request failed.",
                    ) from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise NewsProviderUnavailableError(
                "News provider is unavailable.",
            )

        if response.status_code >= 400:
            raise NewsProviderError(
                f"News provider returned HTTP {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise NewsProviderInvalidResponseError(
                "News provider returned invalid JSON.",
            ) from exc

        if not isinstance(payload, dict):
            raise NewsProviderInvalidResponseError(
                "News provider returned an invalid payload.",
            )

        if payload.get("status") != "ok":
            message = payload.get("message")

            if isinstance(message, str) and message:
                raise NewsProviderError(message)

            raise NewsProviderError(
                "News provider returned an unsuccessful response.",
            )

        return payload

    async def search(
        self,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Sequence[NewsArticle]:
        """Search recent articles using NewsAPI's everything endpoint."""

        normalized_query = query.strip()

        params: dict[str, str] = {
            "q": normalized_query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": "100",
        }

        if start is not None:
            params["from"] = _format_provider_datetime(start)

        if end is not None:
            params["to"] = _format_provider_datetime(end)

        payload = await self._get(
            "/v2/everything",
            params=params,
        )

        return self._normalize_articles(payload)

    async def latest(
        self,
        limit: int = 50,
    ) -> Sequence[NewsArticle]:
        """Return recent market-focused articles."""

        params = {
            "q": self._DEFAULT_LATEST_QUERY,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": str(limit),
        }

        payload = await self._get(
            "/v2/everything",
            params=params,
        )

        return self._normalize_articles(payload)[:limit]

    def _normalize_articles(
        self,
        payload: Mapping[str, object],
    ) -> tuple[NewsArticle, ...]:
        """Normalize and validate provider article records."""

        raw_articles = payload.get("articles")

        if not isinstance(raw_articles, list):
            raise NewsProviderInvalidResponseError(
                "News provider returned an invalid articles collection.",
            )

        normalized: list[NewsArticle] = []

        for raw_article in raw_articles:
            if not isinstance(raw_article, dict):
                raise NewsProviderInvalidResponseError(
                    "News provider returned an invalid article record.",
                )

            normalized.append(self._normalize_article(raw_article))

        return tuple(normalized)

    def _normalize_article(
        self,
        raw_article: Mapping[str, object],
    ) -> NewsArticle:
        """Convert one provider article into the normalized domain model."""

        raw_source = raw_article.get("source")

        if not isinstance(raw_source, dict):
            raise NewsProviderInvalidResponseError(
                "News provider returned an invalid source record.",
            )

        title = raw_article.get("title")
        url = raw_article.get("url")
        published_at = raw_article.get("publishedAt")
        source_name = raw_source.get("name")

        if not isinstance(title, str) or not title.strip():
            raise NewsProviderInvalidResponseError(
                "News provider returned an article without a valid title.",
            )

        if not isinstance(url, str) or not url.strip():
            raise NewsProviderInvalidResponseError(
                "News provider returned an article without a valid URL.",
            )

        if not isinstance(published_at, str) or not published_at.strip():
            raise NewsProviderInvalidResponseError(
                "News provider returned an article without a valid publication time.",
            )

        if not isinstance(source_name, str) or not source_name.strip():
            raise NewsProviderInvalidResponseError(
                "News provider returned an article without a valid source name.",
            )

        source_domain = _extract_domain(url)

        if source_domain is None:
            raise NewsProviderInvalidResponseError(
                "News provider returned an article with an invalid source domain.",
            )

        published_datetime = _parse_provider_datetime(published_at)

        canonical_url = url.strip()
        normalized_title = title.strip()
        content_hash = sha256(
            f"{canonical_url}\n{normalized_title}".encode(),
        ).hexdigest()

        source_id = uuid5(
            NAMESPACE_URL,
            f"marketthread:news-source:{source_domain}",
        )

        summary = raw_article.get("description")
        author = raw_article.get("author")

        if summary is not None and not isinstance(summary, str):
            raise NewsProviderInvalidResponseError(
                "News provider returned an invalid article description.",
            )

        if author is not None and not isinstance(author, str):
            raise NewsProviderInvalidResponseError(
                "News provider returned an invalid article author.",
            )

        try:
            return NewsArticle(
                id=uuid5(
                    NAMESPACE_URL,
                    f"marketthread:news-article:{content_hash}",
                ),
                source_id=source_id,
                source_name=source_name.strip(),
                source_domain=source_domain,
                title=normalized_title,
                url=canonical_url,
                summary=summary,
                author=author,
                published_at=published_datetime,
                discovered_at=datetime.now(UTC),
                content_hash=content_hash,
                language="en",
            )
        except ValueError as exc:
            raise NewsProviderInvalidResponseError(
                "News provider returned an article that could not be normalized.",
            ) from exc


def _extract_domain(url: str) -> str | None:
    """Return a normalized hostname from an article URL."""

    try:
        hostname = urlparse(url).hostname
    except ValueError:
        return None

    if not hostname:
        return None

    normalized = hostname.lower().removeprefix("www.")

    return normalized or None


def _parse_provider_datetime(value: str) -> datetime:
    """Parse an ISO 8601 provider timestamp into UTC."""

    normalized = value.strip().replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise NewsProviderInvalidResponseError(
            "News provider returned an invalid publication time.",
        ) from exc

    if parsed.tzinfo is None:
        raise NewsProviderInvalidResponseError(
            "News provider returned a publication time without timezone information.",
        )

    return parsed.astimezone(UTC)


def _format_provider_datetime(value: datetime) -> str:
    """Format a datetime for NewsAPI."""

    if value.tzinfo is None:
        raise ValueError("News-provider date values must be timezone-aware.")

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

from app.core.config import Settings
from app.news.providers.errors import NewsProviderUnavailableError
from app.news.providers.http import HttpNewsProvider


def create_news_provider(settings: Settings) -> HttpNewsProvider:
    """Create the configured external news provider."""

    if not settings.news_api_key:
        raise NewsProviderUnavailableError(
            "News API key is not configured.",
        )

    return HttpNewsProvider(
        base_url=settings.news_api_base_url,
        api_key=settings.news_api_key,
    )

"""Errors raised by news providers."""


class NewsProviderError(Exception):
    """Base error for news-provider failures."""


class NewsProviderUnavailableError(NewsProviderError):
    """Raised when a news provider cannot serve a request."""


class NewsProviderInvalidResponseError(NewsProviderError):
    """Raised when a provider returns malformed data."""

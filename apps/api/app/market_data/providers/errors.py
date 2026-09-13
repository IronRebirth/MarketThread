"""Errors raised by market-data providers."""


class MarketDataProviderError(Exception):
    """Base error for market-data provider failures."""


class MarketDataNotFoundError(MarketDataProviderError):
    """Raised when a requested market-data resource does not exist."""


class MarketDataUnavailableError(MarketDataProviderError):
    """Raised when a provider cannot currently serve the request."""


class MarketDataInvalidResponseError(MarketDataProviderError):
    """Raised when a provider returns malformed data."""

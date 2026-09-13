from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import httpx

from app.market_data.models import Bar, Instrument, Quote
from app.market_data.providers.errors import (
    MarketDataInvalidResponseError,
    MarketDataNotFoundError,
    MarketDataProviderError,
    MarketDataUnavailableError,
)


class HttpMarketDataProvider:
    """REST-based market-data provider adapter."""

    name = "http"

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        """Build authentication headers for the provider."""

        if not self.api_key:
            return {}

        return {"Authorization": f"Bearer {self.api_key}"}

    async def _get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        """Perform an authenticated provider request."""

        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise MarketDataUnavailableError(
                "Market-data provider request failed.",
            ) from exc

        if response.status_code == 404:
            raise MarketDataNotFoundError(
                "Market-data resource was not found.",
            )

        if response.status_code >= 500:
            raise MarketDataUnavailableError(
                "Market-data provider is unavailable.",
            )

        if response.status_code >= 400:
            raise MarketDataProviderError(
                f"Market-data provider returned HTTP {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketDataInvalidResponseError(
                "Market-data provider returned invalid JSON.",
            ) from exc

        if not isinstance(payload, dict):
            raise MarketDataInvalidResponseError(
                "Market-data provider returned an invalid payload.",
            )

        return payload

    async def get_instrument(
        self,
        symbol: str,
    ) -> Instrument | None:
        """Retrieve and normalize an instrument."""

        try:
            payload = await self._get(
                "/v1/instruments",
                params={"symbol": symbol},
            )
        except MarketDataNotFoundError:
            return None

        try:
            return Instrument.model_validate(payload)
        except ValueError as exc:
            raise MarketDataInvalidResponseError(
                "Provider returned an invalid instrument.",
            ) from exc

    async def get_quote(
        self,
        instrument_id: UUID,
    ) -> Quote | None:
        """Retrieve and normalize the latest quote."""

        try:
            payload = await self._get(
                "/v1/quotes",
                params={"instrument_id": str(instrument_id)},
            )
        except MarketDataNotFoundError:
            return None

        try:
            return Quote.model_validate(payload)
        except ValueError as exc:
            raise MarketDataInvalidResponseError(
                "Provider returned an invalid quote.",
            ) from exc

    async def get_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
    ) -> Sequence[Bar]:
        """Retrieve and normalize historical bars."""

        payload = await self._get(
            "/v1/bars",
            params={
                "instrument_id": str(instrument_id),
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
        )

        raw_bars = payload.get("data")

        if not isinstance(raw_bars, list):
            raise MarketDataInvalidResponseError(
                "Provider returned an invalid bars payload.",
            )

        bars: list[Bar] = []

        try:
            for raw_bar in raw_bars:
                bars.append(Bar.model_validate(raw_bar))
        except ValueError as exc:
            raise MarketDataInvalidResponseError(
                "Provider returned an invalid historical bar.",
            ) from exc

        return bars

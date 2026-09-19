from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.portfolio.application import PortfolioNotFound
from app.portfolio.cash_flow_models import PortfolioCashFlowEventType
from app.portfolio.cash_flow_persistence import (
    PortfolioCashFlowPersistenceService,
)


class PortfolioCashFlowQueryError(ValueError):
    """Raised when a cash-flow history query is invalid."""


class PortfolioCashFlowApplicationService:
    """Application operations for immutable portfolio cash-flow history."""

    def __init__(
        self,
        persistence: PortfolioCashFlowPersistenceService,
    ) -> None:
        self.persistence = persistence

    async def create(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        currency: str,
        amount: Decimal,
        event_type: PortfolioCashFlowEventType,
        effective_at: datetime,
    ):
        """Append a cash-flow event and commit it atomically."""

        try:
            record = await self.persistence.create_for_user(
                user_id=user_id,
                portfolio_id=portfolio_id,
                currency=currency,
                amount=amount,
                event_type=event_type,
                effective_at=effective_at.astimezone(UTC),
            )
        except ValueError as exc:
            raise PortfolioNotFound from exc

        await self.persistence.commit()

        return record

    async def list_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 200,
    ):
        """Return an ownership-safe chronological cash-flow history."""

        normalized_start = self._normalize_boundary(
            start_at,
            "start_at",
        )
        normalized_end = self._normalize_boundary(
            end_at,
            "end_at",
        )

        if (
            normalized_start is not None
            and normalized_end is not None
            and normalized_start > normalized_end
        ):
            raise PortfolioCashFlowQueryError(
                "start_at must not be later than end_at.",
            )

        try:
            return await self.persistence.list_for_user(
                user_id,
                portfolio_id,
                start_at=normalized_start,
                end_at=normalized_end,
                limit=limit,
            )
        except ValueError as exc:
            raise PortfolioNotFound from exc

    @staticmethod
    def _normalize_boundary(
        value: datetime | None,
        label: str,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise PortfolioCashFlowQueryError(
                f"{label} must be timezone-aware",
            )

        return value.astimezone(UTC)

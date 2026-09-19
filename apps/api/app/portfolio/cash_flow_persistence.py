from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.db.models.portfolio import PortfolioRecord
from app.db.models.portfolio_cash_flow import PortfolioCashFlowRecord
from app.portfolio.cash_flow_models import PortfolioCashFlowEventType


class PortfolioCashFlowPersistenceService:
    """Persistence operations for immutable portfolio cash-flow events."""

    def __init__(self, session) -> None:
        self.session = session

    async def create_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        currency: str,
        amount: Decimal,
        event_type: PortfolioCashFlowEventType,
        effective_at: datetime,
    ) -> PortfolioCashFlowRecord:
        """Append a cash-flow event when the portfolio belongs to the user."""

        portfolio_exists = await self.session.scalar(
            select(PortfolioRecord.id).where(
                PortfolioRecord.id == portfolio_id,
                PortfolioRecord.user_id == user_id,
            ),
        )

        if portfolio_exists is None:
            raise ValueError("Portfolio not found.")

        record = PortfolioCashFlowRecord(
            portfolio_id=portfolio_id,
            currency=currency,
            amount=amount,
            event_type=event_type,
            effective_at=effective_at,
        )

        self.session.add(record)
        await self.session.flush()

        return record

    async def list_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int | None = 200,
    ) -> Sequence[PortfolioCashFlowRecord]:
        """Return immutable cash-flow events for a user-owned portfolio."""

        portfolio_exists = await self.session.scalar(
            select(PortfolioRecord.id).where(
                PortfolioRecord.id == portfolio_id,
                PortfolioRecord.user_id == user_id,
            ),
        )

        if portfolio_exists is None:
            raise ValueError("Portfolio not found.")

        statement = select(PortfolioCashFlowRecord).where(
            PortfolioCashFlowRecord.portfolio_id == portfolio_id,
        )

        if start_at is not None:
            statement = statement.where(
                PortfolioCashFlowRecord.effective_at >= start_at,
            )

        if end_at is not None:
            statement = statement.where(
                PortfolioCashFlowRecord.effective_at <= end_at,
            )

        statement = statement.order_by(
            PortfolioCashFlowRecord.effective_at,
            PortfolioCashFlowRecord.sequence_id,
        )

        if limit is not None:
            statement = statement.limit(limit)

        result = await self.session.execute(statement)

        return tuple(result.scalars().all())

    async def commit(self) -> None:
        """Commit the current persistence transaction."""

        await self.session.commit()

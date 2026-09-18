from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.instrument import Instrument as InstrumentRecord
from app.db.models.portfolio import (
    PortfolioPositionRecord,
    PortfolioRecord,
)


class PortfolioPersistenceService:
    """Persist and retrieve user-owned portfolios and positions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: UUID,
        name: str,
    ) -> PortfolioRecord:
        """Create a portfolio for an authenticated user."""

        portfolio = PortfolioRecord(
            user_id=user_id,
            name=name,
        )

        self.session.add(portfolio)
        await self.session.flush()
        await self.session.refresh(portfolio)

        return portfolio

    async def list_for_user(
        self,
        user_id: UUID,
    ) -> Sequence[tuple[PortfolioRecord, int]]:
        """List portfolios with persisted position counts."""

        result = await self.session.execute(
            select(
                PortfolioRecord,
                func.count(PortfolioPositionRecord.id),
            )
            .outerjoin(
                PortfolioPositionRecord,
                PortfolioPositionRecord.portfolio_id == PortfolioRecord.id,
            )
            .where(PortfolioRecord.user_id == user_id)
            .group_by(PortfolioRecord.id)
            .order_by(
                PortfolioRecord.updated_at.desc(),
                PortfolioRecord.id,
            ),
        )

        return tuple(result.all())

    async def get_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
    ) -> tuple[PortfolioRecord, int] | None:
        """Return a portfolio only when it belongs to the user."""

        result = await self.session.execute(
            select(
                PortfolioRecord,
                func.count(PortfolioPositionRecord.id),
            )
            .outerjoin(
                PortfolioPositionRecord,
                PortfolioPositionRecord.portfolio_id == PortfolioRecord.id,
            )
            .where(
                PortfolioRecord.id == portfolio_id,
                PortfolioRecord.user_id == user_id,
            )
            .group_by(PortfolioRecord.id),
        )

        row = result.one_or_none()

        if row is None:
            return None

        return row

    async def list_positions_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
    ) -> Sequence[PortfolioPositionRecord]:
        """Return positions for a user-owned portfolio."""

        result = await self.session.execute(
            select(PortfolioPositionRecord)
            .join(
                PortfolioRecord,
                PortfolioRecord.id == PortfolioPositionRecord.portfolio_id,
            )
            .where(
                PortfolioRecord.id == portfolio_id,
                PortfolioRecord.user_id == user_id,
            )
            .order_by(
                PortfolioPositionRecord.created_at,
                PortfolioPositionRecord.id,
            ),
        )

        return tuple(result.scalars().all())

    async def get_detail_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
    ) -> tuple[PortfolioRecord, int, Sequence[PortfolioPositionRecord]] | None:
        """Return a portfolio, position count, and positions for its owner."""

        portfolio = await self.get_for_user(
            user_id,
            portfolio_id,
        )

        if portfolio is None:
            return None

        positions = await self.list_positions_for_user(
            user_id,
            portfolio_id,
        )

        portfolio_record, position_count = portfolio

        return (
            portfolio_record,
            position_count,
            positions,
        )

    async def upsert_position(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        instrument_id: UUID,
        quantity,
        average_cost,
    ) -> tuple[PortfolioPositionRecord, bool]:
        """Create or replace the current position for an instrument."""

        portfolio = await self.get_for_user(
            user_id,
            portfolio_id,
        )

        if portfolio is None:
            raise ValueError("Portfolio not found.")

        instrument = await self.session.scalar(
            select(InstrumentRecord).where(
                InstrumentRecord.id == instrument_id,
                InstrumentRecord.is_active.is_(True),
            ),
        )

        if instrument is None:
            raise LookupError("Instrument not found.")

        existing = await self.session.scalar(
            select(PortfolioPositionRecord).where(
                PortfolioPositionRecord.portfolio_id == portfolio_id,
                PortfolioPositionRecord.instrument_id == instrument_id,
            ),
        )

        created = existing is None

        if existing is None:
            existing = PortfolioPositionRecord(
                portfolio_id=portfolio_id,
                instrument_id=instrument_id,
                quantity=quantity,
                average_cost=average_cost,
            )
            self.session.add(existing)
        else:
            existing.quantity = quantity
            existing.average_cost = average_cost

        await self.session.flush()
        await self.session.refresh(existing)

        return existing, created

    async def get_position_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        position_id: UUID,
    ) -> PortfolioPositionRecord | None:
        """Return a position only when it belongs to the user's portfolio."""

        result = await self.session.execute(
            select(PortfolioPositionRecord)
            .join(
                PortfolioRecord,
                PortfolioRecord.id == PortfolioPositionRecord.portfolio_id,
            )
            .where(
                PortfolioPositionRecord.id == position_id,
                PortfolioPositionRecord.portfolio_id == portfolio_id,
                PortfolioRecord.user_id == user_id,
            ),
        )

        return result.scalar_one_or_none()

    async def delete_position_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        position_id: UUID,
    ) -> bool:
        """Delete a position only when it belongs to the user's portfolio."""

        position = await self.get_position_for_user(
            user_id,
            portfolio_id,
            position_id,
        )

        if position is None:
            return False

        await self.session.delete(position)
        await self.session.flush()

        return True

    async def delete_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
    ) -> bool:
        """Delete a portfolio only when it belongs to the user."""

        portfolio = await self.session.scalar(
            select(PortfolioRecord).where(
                PortfolioRecord.id == portfolio_id,
                PortfolioRecord.user_id == user_id,
            ),
        )

        if portfolio is None:
            return False

        await self.session.delete(portfolio)
        await self.session.flush()

        return True

    async def commit(self) -> None:
        """Commit the current persistence transaction."""

        await self.session.commit()

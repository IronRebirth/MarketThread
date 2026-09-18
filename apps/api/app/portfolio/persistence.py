from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.instrument import Instrument as InstrumentRecord
from app.db.models.portfolio import (
    PortfolioPositionRecord,
    PortfolioRecord,
)
from app.db.models.portfolio_history import PortfolioPositionHistoryRecord


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
        quantity: Decimal,
        average_cost: Decimal,
    ) -> tuple[PortfolioPositionRecord, bool]:
        """Create or replace the current position and record its history."""

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
            event_type = "created"
        else:
            existing.quantity = quantity
            existing.average_cost = average_cost
            event_type = "updated"

        await self.session.flush()
        await self.session.refresh(existing)

        history = PortfolioPositionHistoryRecord(
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            quantity=existing.quantity,
            average_cost=existing.average_cost,
            event_type=event_type,
        )
        self.session.add(history)

        await self.session.flush()

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
        """Record position removal before deleting its current state."""

        position = await self.get_position_for_user(
            user_id,
            portfolio_id,
            position_id,
        )

        if position is None:
            return False

        history = PortfolioPositionHistoryRecord(
            portfolio_id=position.portfolio_id,
            instrument_id=position.instrument_id,
            quantity=Decimal("0"),
            average_cost=position.average_cost,
            event_type="deleted",
        )
        self.session.add(history)

        await self.session.delete(position)
        await self.session.flush()

        return True

    async def list_position_history_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        instrument_id: UUID | None = None,
    ) -> Sequence[PortfolioPositionHistoryRecord]:
        """Return historical position states for a user-owned portfolio."""

        statement = (
            select(PortfolioPositionHistoryRecord)
            .join(
                PortfolioRecord,
                PortfolioRecord.id == PortfolioPositionHistoryRecord.portfolio_id,
            )
            .where(
                PortfolioPositionHistoryRecord.portfolio_id == portfolio_id,
                PortfolioRecord.user_id == user_id,
            )
            .order_by(
                PortfolioPositionHistoryRecord.sequence_id,
            )
        )

        if instrument_id is not None:
            statement = statement.where(
                PortfolioPositionHistoryRecord.instrument_id == instrument_id,
            )

        result = await self.session.execute(statement)

        return tuple(result.scalars().all())

    async def list_position_history_at(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        as_of,
    ) -> Sequence[PortfolioPositionHistoryRecord]:
        """Return the latest historical state for each instrument at a point in time."""

        history_rank = (
            func.row_number()
            .over(
                partition_by=PortfolioPositionHistoryRecord.instrument_id,
                order_by=(
                    PortfolioPositionHistoryRecord.recorded_at.desc(),
                    PortfolioPositionHistoryRecord.sequence_id.desc(),
                ),
            )
            .label("history_rank")
        )

        latest_history = (
            select(
                PortfolioPositionHistoryRecord.sequence_id.label("sequence_id"),
                history_rank,
            )
            .join(
                PortfolioRecord,
                PortfolioRecord.id == PortfolioPositionHistoryRecord.portfolio_id,
            )
            .where(
                PortfolioPositionHistoryRecord.portfolio_id == portfolio_id,
                PortfolioRecord.user_id == user_id,
                PortfolioPositionHistoryRecord.recorded_at <= as_of,
            )
            .subquery()
        )

        result = await self.session.execute(
            select(PortfolioPositionHistoryRecord)
            .join(
                latest_history,
                latest_history.c.sequence_id
                == PortfolioPositionHistoryRecord.sequence_id,
            )
            .where(
                latest_history.c.history_rank == 1,
            )
            .order_by(
                PortfolioPositionHistoryRecord.instrument_id,
                PortfolioPositionHistoryRecord.sequence_id,
            ),
        )

        return tuple(result.scalars().all())

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

from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.db.models.portfolio import PortfolioPositionRecord, PortfolioRecord
from app.portfolio.persistence import PortfolioPersistenceService


class PortfolioNotFound(Exception):
    """Raised when a requested portfolio does not belong to the user."""


class PortfolioNameConflict(Exception):
    """Raised when a user already has a portfolio with the same name."""


class PortfolioInstrumentNotFound(Exception):
    """Raised when a requested active instrument does not exist."""


class PortfolioPositionNotFound(Exception):
    """Raised when a requested position does not belong to the user."""


class PortfolioApplicationService:
    """Application operations for user-owned portfolios."""

    def __init__(self, persistence: PortfolioPersistenceService) -> None:
        self.persistence = persistence

    async def create(
        self,
        user_id: UUID,
        name: str,
    ) -> PortfolioRecord:
        """Create a portfolio and commit its transaction."""

        try:
            portfolio = await self.persistence.create(
                user_id=user_id,
                name=name,
            )
            await self.persistence.commit()
        except IntegrityError as exc:
            await self.persistence.session.rollback()

            if "uq_portfolios_user_name" in str(exc):
                raise PortfolioNameConflict from exc

            raise

        return portfolio

    async def list_for_user(
        self,
        user_id: UUID,
    ):
        """List portfolios owned by the user."""

        return await self.persistence.list_for_user(user_id)

    async def get_detail_for_user(
        self,
        user_id: UUID,
        portfolio_id: UUID,
    ):
        """Return a portfolio and its positions."""

        detail = await self.persistence.get_detail_for_user(
            user_id,
            portfolio_id,
        )

        if detail is None:
            raise PortfolioNotFound

        return detail

    async def upsert_position(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        instrument_id: UUID,
        quantity: Decimal,
        average_cost: Decimal,
    ) -> tuple[PortfolioPositionRecord, bool]:
        """Create or replace a portfolio position."""

        try:
            position, created = await self.persistence.upsert_position(
                user_id=user_id,
                portfolio_id=portfolio_id,
                instrument_id=instrument_id,
                quantity=quantity,
                average_cost=average_cost,
            )
        except ValueError as exc:
            raise PortfolioNotFound from exc
        except LookupError as exc:
            raise PortfolioInstrumentNotFound from exc

        await self.persistence.commit()

        return position, created

    async def delete_position(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        position_id: UUID,
    ) -> None:
        """Delete a user-owned portfolio position."""

        deleted = await self.persistence.delete_position_for_user(
            user_id,
            portfolio_id,
            position_id,
        )

        if not deleted:
            raise PortfolioPositionNotFound

        await self.persistence.commit()

    async def delete(
        self,
        user_id: UUID,
        portfolio_id: UUID,
    ) -> None:
        """Delete a user-owned portfolio."""

        deleted = await self.persistence.delete_for_user(
            user_id,
            portfolio_id,
        )

        if not deleted:
            raise PortfolioNotFound

        await self.persistence.commit()

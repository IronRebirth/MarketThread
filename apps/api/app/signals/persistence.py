from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.signal import SignalRecord

from .models import MarketSignal


class SignalPersistenceError(Exception):
    """Base error for signal persistence."""


class SignalNotFoundError(SignalPersistenceError):
    """Raised when a persisted signal does not exist."""


class SignalPersistenceService:
    """Persist immutable market signal snapshots."""

    async def create(
        self,
        session: AsyncSession,
        *,
        signal: MarketSignal,
        instrument_id: UUID,
        created_at: datetime,
        signal_id: UUID | None = None,
        market_impact_id: UUID | None = None,
    ) -> SignalRecord:
        if market_impact_id is not None:
            existing = await session.scalar(
                select(SignalRecord).where(
                    SignalRecord.market_impact_id == market_impact_id,
                ),
            )

            if existing is not None:
                return existing

        record = SignalRecord(
            id=signal_id or uuid4(),
            market_impact_id=market_impact_id,
            event_id=signal.event_id,
            instrument_id=instrument_id,
            company_name=signal.company_name,
            ticker=signal.ticker,
            created_at=created_at,
            direction=signal.direction.value,
            strength=signal.strength.value,
            opportunity=signal.opportunity.value,
            confidence=signal.confidence,
            risk_score=signal.risk_score,
            time_horizon=signal.time_horizon,
            supporting_factors=list(signal.supporting_factors),
            contradicting_factors=list(signal.contradicting_factors),
            evidence_article_ids=[
                str(article_id) for article_id in signal.evidence_article_ids
            ],
            invalidation_conditions=list(signal.invalidation_conditions),
            rationale=signal.rationale,
        )

        session.add(record)

        await session.commit()
        await session.refresh(record)

        return record

    async def get(
        self,
        session: AsyncSession,
        signal_id: UUID,
    ) -> SignalRecord:
        record = await session.get(
            SignalRecord,
            signal_id,
        )

        if record is None:
            raise SignalNotFoundError(
                f"Signal {signal_id} was not found.",
            )

        return record

    async def list(
        self,
        session: AsyncSession,
        *,
        instrument_id: UUID | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
    ) -> tuple[SignalRecord, ...]:
        statement = select(SignalRecord)

        if instrument_id is not None:
            statement = statement.where(
                SignalRecord.instrument_id == instrument_id,
            )

        if start_at is not None:
            statement = statement.where(
                SignalRecord.created_at >= start_at,
            )

        if end_at is not None:
            statement = statement.where(
                SignalRecord.created_at < end_at,
            )

        statement = statement.order_by(
            SignalRecord.created_at.desc(),
        ).limit(limit)

        result = await session.execute(statement)

        return tuple(result.scalars().all())

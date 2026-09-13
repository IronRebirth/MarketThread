import uuid

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Instrument(Base):
    """Tradeable market instrument."""

    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "exchange",
            name="uq_instruments_symbol_exchange",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    exchange: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    asset_class: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def create_engine() -> AsyncEngine:
    """Create the SQLAlchemy asynchronous engine."""

    settings = get_settings()

    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


engine = create_engine()

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for an application request."""

    async with SessionFactory() as session:
        yield session

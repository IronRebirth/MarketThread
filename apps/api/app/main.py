from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.market_data import router as market_data_router
from app.backtesting.api import router as backtesting_router
from app.company_impact.api import router as company_impact_router
from app.core.config import get_settings
from app.events.api import router as events_router
from app.market_impact.api import router as market_impact_router
from app.news.api import router as news_router
from app.portfolio.api import router as portfolio_router
from app.portfolio.event_sensitivity_api import (
    router as portfolio_event_sensitivity_router,
)
from app.portfolio.performance_api import router as portfolio_performance_router
from app.portfolio.risk_metrics_api import router as portfolio_risk_metrics_router
from app.recommendations.api import router as recommendations_router
from app.signals.api import router as signals_router
from app.watchlists.api import router as watchlists_router

settings = get_settings()

app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.1.0",
    description=("Backend API for the MarketThread financial intelligence platform."),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(market_data_router)
app.include_router(backtesting_router)
app.include_router(news_router)
app.include_router(events_router)
app.include_router(company_impact_router)
app.include_router(market_impact_router)
app.include_router(signals_router)
app.include_router(recommendations_router)
app.include_router(watchlists_router)
app.include_router(portfolio_router)
app.include_router(portfolio_event_sensitivity_router)
app.include_router(portfolio_risk_metrics_router)
app.include_router(portfolio_performance_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return the basic health status of the API."""

    return {"status": "healthy"}


@app.get("/ready", tags=["system"])
async def readiness() -> dict[str, str]:
    """Return the readiness status of the API."""

    return {"status": "ready"}

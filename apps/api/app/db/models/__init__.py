"""SQLAlchemy models for MarketThread."""

from app.db.models.backtest import (
    BacktestEvaluation,
    BacktestFold,
    BacktestRun,
)
from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord
from app.db.models.fundamental_snapshot import FundamentalSnapshot
from app.db.models.instrument import Instrument
from app.db.models.market_bar import MarketBar
from app.db.models.market_data import MarketQuote
from app.db.models.market_impact import MarketImpactRecord
from app.db.models.model_monitoring_snapshot import ModelMonitoringSnapshot
from app.db.models.news import NewsArticle, NewsSource
from app.db.models.notification_email_delivery import (
    NotificationEmailDeliveryRecord,
)
from app.db.models.portfolio import (
    PortfolioPositionRecord,
    PortfolioRecord,
)
from app.db.models.portfolio_history import PortfolioPositionHistoryRecord
from app.db.models.provenance import BacktestProvenance
from app.db.models.recommendation import RecommendationRecord
from app.db.models.recommendation_provenance import (
    RecommendationProvenanceRecord,
)
from app.db.models.signal import SignalRecord
from app.db.models.user import User
from app.db.models.watchlist import WatchlistItemRecord, WatchlistRecord
from app.db.models.watchlist_alert_rule import WatchlistAlertRuleRecord
from app.db.models.watchlist_alert_state import WatchlistAlertStateRecord
from app.db.models.watchlist_notification import WatchlistNotificationRecord

__all__ = [
    "BacktestEvaluation",
    "BacktestFold",
    "BacktestProvenance",
    "BacktestRun",
    "CompanyImpactRecord",
    "EventRecord",
    "FundamentalSnapshot",
    "Instrument",
    "MarketBar",
    "MarketImpactRecord",
    "ModelMonitoringSnapshot",
    "MarketQuote",
    "NewsArticle",
    "NewsSource",
    "NotificationEmailDeliveryRecord",
    "PortfolioPositionHistoryRecord",
    "PortfolioPositionRecord",
    "PortfolioRecord",
    "RecommendationProvenanceRecord",
    "RecommendationRecord",
    "SignalRecord",
    "User",
    "WatchlistAlertRuleRecord",
    "WatchlistAlertStateRecord",
    "WatchlistItemRecord",
    "WatchlistNotificationRecord",
    "WatchlistRecord",
]

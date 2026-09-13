from enum import StrEnum


class EventType(StrEnum):
    """Normalized market event categories."""

    MONETARY_POLICY = "monetary_policy"
    INFLATION = "inflation"
    TRADE_POLICY = "trade_policy"
    GEOPOLITICAL = "geopolitical"
    CORPORATE_ACTION = "corporate_action"
    EARNINGS = "earnings"
    REGULATION = "regulation"
    MACROECONOMIC = "macroeconomic"
    OTHER = "other"


class EventCatalyst(StrEnum):
    """Normalized catalysts that can drive a market event."""

    RATE_CUT = "rate_cut"
    RATE_HIKE = "rate_hike"
    INFLATION_SURPRISE = "inflation_surprise"
    TARIFF = "tariff"
    SANCTION = "sanction"
    MILITARY_ESCALATION = "military_escalation"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    EARNINGS_SURPRISE = "earnings_surprise"
    REGULATORY_CHANGE = "regulatory_change"
    OTHER = "other"

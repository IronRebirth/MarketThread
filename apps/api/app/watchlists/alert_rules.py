from collections.abc import Sequence

from app.watchlists.alert_rule_models import (
    AlertRuleType,
    WatchlistAlertRule,
)
from app.watchlists.alerts_models import WatchlistAlert


class WatchlistAlertRuleService:
    """Evaluate notification eligibility against derived watchlist alerts."""

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower()

    @classmethod
    def matches(
        cls,
        *,
        alert: WatchlistAlert,
        rule: WatchlistAlertRule,
    ) -> bool:
        """Return whether one alert satisfies one enabled rule."""

        if not rule.enabled:
            return False

        if rule.rule_type != AlertRuleType.EVENT_IMPACT:
            return False

        conditions = rule.conditions

        if conditions.event_types:
            allowed_event_types = {
                cls._normalize(value)
                for value in conditions.event_types
            }

            if cls._normalize(alert.event_type) not in allowed_event_types:
                return False

        if conditions.directions:
            allowed_directions = {
                cls._normalize(value)
                for value in conditions.directions
            }

            if cls._normalize(alert.direction) not in allowed_directions:
                return False

        if (
            conditions.minimum_confidence is not None
            and alert.confidence < conditions.minimum_confidence
        ):
            return False

        if (
            conditions.minimum_event_confidence is not None
            and alert.event_confidence < conditions.minimum_event_confidence
        ):
            return False

        return True

    @classmethod
    def select_matching_alerts(
        cls,
        *,
        alerts: Sequence[WatchlistAlert],
        rules: Sequence[WatchlistAlertRule],
    ) -> tuple[WatchlistAlert, ...]:
        """Return alerts matching at least one enabled rule.

        Rules use OR semantics. No enabled rules means no notification-eligible
        alerts.
        """

        enabled_rules = tuple(rule for rule in rules if rule.enabled)

        if not enabled_rules:
            return ()

        return tuple(
            alert
            for alert in alerts
            if any(
                cls.matches(
                    alert=alert,
                    rule=rule,
                )
                for rule in enabled_rules
            )
        )

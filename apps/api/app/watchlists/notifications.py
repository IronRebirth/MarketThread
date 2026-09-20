from collections.abc import Sequence

from app.watchlists.alert_rule_models import WatchlistAlertRule
from app.watchlists.alerts_models import WatchlistAlert


class WatchlistNotificationService:
    """Select alert-rule matches that should become in-app notifications."""

    @staticmethod
    def matching_pairs(
        *,
        alerts: Sequence[WatchlistAlert],
        rules: Sequence[WatchlistAlertRule],
    ) -> tuple[tuple[WatchlistAlertRule, WatchlistAlert], ...]:
        """Return one pair for every enabled rule matched by an alert."""

        return tuple(
            (rule, alert)
            for alert in alerts
            for rule in rules
            if rule.enabled
            and WatchlistNotificationService._matches(
                alert=alert,
                rule=rule,
            )
        )

    @staticmethod
    def _matches(
        *,
        alert: WatchlistAlert,
        rule: WatchlistAlertRule,
    ) -> bool:
        from app.watchlists.alert_rules import WatchlistAlertRuleService

        return WatchlistAlertRuleService.matches(
            alert=alert,
            rule=rule,
        )

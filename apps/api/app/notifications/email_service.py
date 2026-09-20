import smtplib
from email.message import EmailMessage

from app.core.config import Settings
from app.watchlists.notification_models import WatchlistNotification


class EmailDeliveryConfigurationError(Exception):
    """Raised when SMTP configuration is incomplete or invalid."""


class EmailDeliveryError(Exception):
    """Raised when an email cannot be delivered."""


class NotificationEmailService:
    """Send persisted watchlist notifications through configured SMTP."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(
        self,
        *,
        recipient_email: str,
        notification: WatchlistNotification,
    ) -> None:
        """Deliver one notification email using SMTP."""

        host = self.settings.smtp_host

        if not host:
            raise EmailDeliveryConfigurationError(
                "SMTP_HOST is not configured.",
            )

        port = self.settings.smtp_port

        if port < 1 or port > 65535:
            raise EmailDeliveryConfigurationError(
                "SMTP_PORT must be between 1 and 65535.",
            )

        from_email = self.settings.smtp_from_email

        if not from_email:
            raise EmailDeliveryConfigurationError(
                "SMTP_FROM_EMAIL is not configured.",
            )

        if self.settings.smtp_username and not self.settings.smtp_password:
            raise EmailDeliveryConfigurationError(
                "SMTP_PASSWORD is required when SMTP_USERNAME is configured.",
            )

        message = EmailMessage()
        message["Subject"] = f"MarketThread alert: {notification.symbol}"
        message["From"] = from_email
        message["To"] = recipient_email
        message.set_content(
            "\n".join(
                (
                    "MarketThread watchlist notification",
                    "",
                    notification.title,
                    "",
                    notification.message,
                    "",
                    f"Watchlist rule: {notification.rule_name}",
                    f"Event type: {notification.event_type}",
                    f"Direction: {notification.direction}",
                    f"Confidence: {notification.confidence:.0%}",
                    "",
                    "This notification is based on persisted MarketThread "
                    "intelligence and is not a guarantee of future market "
                    "outcomes.",
                ),
            ),
        )

        try:
            with smtplib.SMTP(
                host,
                port,
                timeout=self.settings.smtp_timeout,
            ) as smtp:
                smtp.ehlo()

                if self.settings.smtp_use_tls:
                    smtp.starttls()
                    smtp.ehlo()

                if self.settings.smtp_username:
                    smtp.login(
                        self.settings.smtp_username,
                        self.settings.smtp_password,
                    )

                smtp.send_message(message)
        except EmailDeliveryConfigurationError:
            raise
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError(
                "SMTP delivery failed.",
            ) from exc

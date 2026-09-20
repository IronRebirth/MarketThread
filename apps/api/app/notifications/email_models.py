from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationEmailDelivery(BaseModel):
    """Domain representation of one notification email delivery."""

    model_config = ConfigDict(frozen=True)

    delivery_id: UUID
    notification_id: UUID
    recipient_email: str
    status: str
    attempt_count: int
    last_error: str | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

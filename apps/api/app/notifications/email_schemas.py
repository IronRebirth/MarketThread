from pydantic import BaseModel, ConfigDict, Field


class EmailNotificationPreferencesResponse(BaseModel):
    """Email notification preference for the authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    enabled: bool


class EmailNotificationPreferencesUpdateRequest(BaseModel):
    """Update request for the authenticated user's email preference."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool


class EmailNotificationDispatchResponse(BaseModel):
    """Summary of an explicit email notification dispatch."""

    enabled: bool
    eligible_count: int = Field(ge=0)
    sent_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)

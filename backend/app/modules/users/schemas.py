import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    followup_ready: bool = True
    status_changes: bool = True


class PrivacySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_name_in_complaints: bool = True
    share_exact_coordinates: bool = True


class SettingsUpdate(BaseModel):
    notification_preferences: NotificationPreferences
    privacy_settings: PrivacySettings


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain a letter and a number.")
        return value


class UserRead(BaseModel):
    """The public view of a user. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    created_at: datetime
    notification_preferences: NotificationPreferences = Field(
        default_factory=NotificationPreferences
    )
    privacy_settings: PrivacySettings = Field(default_factory=PrivacySettings)


def clean_name(value: str) -> str:
    """Trim and collapse internal whitespace: '  Asha   Rao ' -> 'Asha Rao'."""
    return " ".join(value.split())


class UserUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, value: object) -> object:
        return clean_name(value) if isinstance(value, str) else value

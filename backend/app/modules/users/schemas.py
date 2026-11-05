import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRead(BaseModel):
    """The public view of a user. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    created_at: datetime


def clean_name(value: str) -> str:
    """Trim and collapse internal whitespace: '  Asha   Rao ' -> 'Asha Rao'."""
    return " ".join(value.split())


class UserUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, value: object) -> object:
        return clean_name(value) if isinstance(value, str) else value

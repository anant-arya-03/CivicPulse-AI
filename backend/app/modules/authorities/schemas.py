import uuid
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.common.time import utc_now
from app.modules.complaints.constants import Category

JurisdictionLevel = Literal["WARD", "CITY", "DISTRICT", "STATE", "NATIONAL"]


class AuthorityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    jurisdiction: str
    jurisdiction_level: str
    city: str | None
    state: str | None
    country: str
    supported_categories: list[str]
    official_email: str | None
    official_phone: str | None
    website_url: str | None
    source_url: str | None
    verified_at: date | None
    verification_notes: str | None
    service_timeline_days: int | None
    parent_authority_id: uuid.UUID | None
    is_demo: bool


class AuthorityMatchRead(BaseModel):
    authority: AuthorityRead
    score: int
    reasons: list[str]


class AuthorityMatchesResponse(BaseModel):
    confidence: Literal["EXACT", "PARTIAL", "NONE"]
    matches: list[AuthorityMatchRead]
    selected_authority_id: uuid.UUID | None


class SelectAuthorityRequest(BaseModel):
    authority_id: uuid.UUID


class AuthorityImport(BaseModel):
    """One REAL department for scripts/import_authorities.py. Every field a citizen relies on
    must come from an official source, recorded in source_url and verified_at."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=200)
    jurisdiction: str = Field(min_length=2, max_length=200)
    jurisdiction_level: JurisdictionLevel
    city: str | None = Field(None, max_length=120)
    state: str | None = Field(None, max_length=120)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    supported_categories: list[Category]
    official_email: EmailStr | None = None
    official_phone: str | None = Field(None, max_length=40)
    website_url: HttpUrl | None = None
    source_url: HttpUrl
    verified_at: date
    verification_notes: str | None = None
    service_timeline_days: int | None = Field(None, ge=1, le=365)
    parent_name: str | None = None

    @field_validator("source_url")
    @classmethod
    def _https_source(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("source_url must be an https:// link to the official page.")
        return value

    @field_validator("verified_at")
    @classmethod
    def _recently_verified(cls, value: date) -> date:
        today = utc_now().date()
        # One day of slack: "today" in India or Australia can already be tomorrow in UTC.
        if value > today + timedelta(days=1):
            raise ValueError("verified_at can't be in the future.")
        if value < today - timedelta(days=365):
            raise ValueError("verified_at is over a year old. Check the source again first.")
        return value

    @field_validator("official_email")
    @classmethod
    def _no_reserved_domains(cls, value: str | None) -> str | None:
        if value and value.lower().rsplit("@", 1)[-1].split(".")[-1] in {
            "example",
            "test",
            "invalid",
        }:
            raise ValueError("Reserved demo domains are only allowed in demo records.")
        return value

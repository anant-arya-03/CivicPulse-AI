import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.pagination import PageParams
from app.common.time import utc_now
from app.modules.authorities.schemas import AuthorityRead
from app.modules.complaints.constants import Category, ComplaintStatus, Severity
from app.modules.evidence.schemas import EvidenceRead

_SINGLE_LINE_FIELDS = (
    "title",
    "draft_subject",
    "address_line",
    "locality",
    "city",
    "state",
    "postal_code",
    "country",
)


class ComplaintFields(BaseModel):
    """Fields a citizen can set. Every field is optional because a draft is filled in step by
    step. Send only the fields you want to change."""

    title: str | None = Field(None, min_length=5, max_length=160)
    description: str | None = Field(None, max_length=5000)
    category: Category | None = None
    severity: Severity | None = None

    address_line: str | None = Field(None, max_length=255)
    locality: str | None = Field(None, max_length=120)
    city: str | None = Field(None, max_length=120)
    state: str | None = Field(None, max_length=120)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, pattern=r"^[A-Z]{2}$", description="ISO 3166 alpha-2")
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    observed_at: datetime | None = None
    draft_subject: str | None = Field(None, min_length=5, max_length=200)
    draft_body: str | None = Field(None, min_length=20, max_length=10000)

    @field_validator(*_SINGLE_LINE_FIELDS, mode="before")
    @classmethod
    def _clean_single_line(cls, value: object) -> object:
        """'  Main   St ' -> 'Main St'. An empty string means 'no value'."""
        if not isinstance(value, str):
            return value
        return " ".join(value.split()) or None

    @field_validator("description", "draft_body", mode="before")
    @classmethod
    def _clean_description(cls, value: object) -> object:
        """Trim the ends but keep the citizen's line breaks."""
        if not isinstance(value, str):
            return value
        return value.strip() or None

    @field_validator("country", mode="before")
    @classmethod
    def _upper_country(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("observed_at")
    @classmethod
    def _not_in_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("Include a time zone (e.g. 2026-11-03T10:00:00Z).")
        if value > utc_now() + timedelta(minutes=5):
            raise ValueError("The observation time can't be in the future.")
        return value

    @model_validator(mode="after")
    def _coordinates_together(self) -> "ComplaintFields":
        sent = self.model_fields_set
        if ("latitude" in sent) != ("longitude" in sent) or (
            (self.latitude is None) != (self.longitude is None)
        ):
            raise ValueError("Send latitude and longitude together.")
        return self


class ComplaintCreate(ComplaintFields):
    pass


class ComplaintUpdate(ComplaintFields):
    confirm_location: bool = Field(
        False, description="Set true when the citizen confirms the incident location."
    )


class ComplaintListParams(PageParams):
    search: str | None = Field(None, max_length=100)
    category: Category | None = None
    status: ComplaintStatus | None = None
    sort: Literal["-created_at", "created_at", "-updated_at"] = "-created_at"


ComplaintAction = Literal["edit", "add_photo", "cancel", "close", "submit", "verify", "reopen"]


class ComplaintListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    public_reference: str
    title: str | None
    category: Category | None
    severity: Severity | None
    status: ComplaintStatus
    locality: str | None
    city: str | None
    thumbnail_url: str | None = None
    created_at: datetime
    updated_at: datetime


class ComplaintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    public_reference: str
    title: str | None
    description: str | None
    category: Category | None
    severity: Severity | None
    status: ComplaintStatus
    address_line: str | None
    locality: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
    location_confirmed_at: datetime | None
    observed_at: datetime | None
    draft_subject: str | None
    draft_body: str | None
    authority: AuthorityRead | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    evidence: list[EvidenceRead]
    available_actions: list[ComplaintAction] = []


class ComplaintEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    previous_status: ComplaintStatus | None
    new_status: ComplaintStatus | None
    description: str
    actor: str
    created_at: datetime


class ActivityItem(ComplaintEventRead):
    complaint_id: uuid.UUID
    complaint_reference: str
    complaint_title: str | None


class DashboardStats(BaseModel):
    total: int  # every complaint except cancelled ones
    drafts: int  # DRAFT or PENDING_REVIEW
    active: int  # sent to a department and not finished
    pending_responses: int  # SUBMITTED, waiting for the department's first reply
    verified_resolutions: int  # the citizen confirmed the fix


class AttentionItem(BaseModel):
    """Something the citizen should do on a complaint (one item per complaint, most urgent)."""

    complaint_id: uuid.UUID
    complaint_reference: str
    complaint_title: str | None
    kind: Literal[
        "VERIFY_FIX",
        "FOLLOWUP_FAILED",
        "FOLLOWUP_READY",
        "REPLY_TO_REVIEW",
        "INFO_REQUESTED",
        "ESCALATION",
    ]
    message: str


class DashboardSummary(BaseModel):
    stats: DashboardStats
    recent_complaints: list[ComplaintListItem]
    recent_activity: list[ActivityItem]
    needs_attention: list[AttentionItem]

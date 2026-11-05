import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.authorities.schemas import AuthorityRead


class CommunicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    direction: str
    communication_type: str
    channel: str
    recipient: str | None
    sender: str | None
    subject: str
    body: str
    attachments: list[dict[str, Any]]
    delivery_status: str
    is_simulated: bool
    provider: str | None
    attempt_count: int
    error_message: str | None
    sent_at: datetime | None
    received_at: datetime | None
    created_at: datetime
    followup_number: int | None
    reply_kind: str | None
    reply_kind_source: str | None
    reply_summary: str | None
    reference_number: str | None


class PreviewAttachment(BaseModel):
    evidence_id: uuid.UUID
    url: str
    file_type: str


class SubmissionPreview(BaseModel):
    ready: bool
    missing: list[str]  # what to finish first, e.g. "a department"
    authority: AuthorityRead | None
    recipient: str | None
    from_address: str
    subject: str | None
    body: str | None
    attachments: list[PreviewAttachment]
    is_simulated: bool  # true = nothing will reach a real department
    content_sha256: str | None  # send this back when approving
    pending_communication: CommunicationRead | None  # approved but not yet sent


class ApproveRequest(BaseModel):
    confirm: Literal[True] = Field(description="The citizen ticked 'I approve sending this'.")
    content_sha256: str = Field(
        min_length=64,
        max_length=64,
        description="The hash from the preview the citizen looked at.",
    )


class FollowupUpdate(BaseModel):
    """The citizen edits a suggested reminder before approving it (send only changed fields)."""

    subject: str | None = Field(None, min_length=5, max_length=200)
    body: str | None = Field(None, min_length=20, max_length=10_000)

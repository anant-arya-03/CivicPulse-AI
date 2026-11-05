import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.authorities.schemas import AuthorityRead
from app.modules.communications.schemas import CommunicationRead
from app.modules.monitoring.constants import ReplyKind


class ScheduledActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action_type: str
    scheduled_at: datetime
    execution_status: str
    attempt_count: int
    outcome: str | None
    executed_at: datetime | None


class EscalationRead(BaseModel):
    recommended_at: datetime
    reason: str
    # Only active directory records with a contact. Demo records keep their is_demo flag.
    contacts: list[AuthorityRead]


class MonitoringRead(BaseModel):
    """Everything the complaint page needs to show response tracking."""

    monitored: bool  # waiting for the department (reminders possible)
    response_due_at: datetime | None  # when CivicPulse next checks for a reply
    deadline_basis: str | None  # why that date, in plain words
    deadline_official: bool  # based on the department's listed response time
    followups_sent: int
    followups_max: int
    authority_reference_number: str | None
    open_followup: CommunicationRead | None  # a reminder waiting for approval (or a retry)
    open_followup_sha256: str | None  # hash of its current content, needed to approve it
    replies_to_review: list[CommunicationRead]  # replies whose meaning the citizen must set
    latest_reply: CommunicationRead | None
    escalation: EscalationRead | None


class ReplyKindRequest(BaseModel):
    kind: ReplyKind


class SimulationInfo(BaseModel):
    enabled: bool
    reply_scenarios: list[dict[str, str]]  # [{"id": "acknowledged", "label": "..."}]


class SimulateReplyRequest(BaseModel):
    """Either a named sample reply or custom text (exactly one)."""

    scenario: (
        Literal[
            "acknowledged",
            "in_progress",
            "resolved",
            "need_info",
            "rejected",
            "auto_reply",
            "injection",
        ]
        | None
    ) = None
    body: str | None = Field(None, min_length=5, max_length=5000)

    @model_validator(mode="after")
    def _exactly_one(self) -> "SimulateReplyRequest":
        if (self.scenario is None) == (self.body is None):
            raise ValueError("Send either a scenario or a body.")
        return self


class AdvanceResult(BaseModel):
    ran: list[ScheduledActionRead]

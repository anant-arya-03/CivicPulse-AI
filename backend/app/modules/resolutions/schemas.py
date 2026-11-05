import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.evidence.schemas import EvidenceRead


class CreateReviewRequest(BaseModel):
    evidence_id: uuid.UUID = Field(description="The follow-up ('after') photo to compare.")


class DecisionRequest(BaseModel):
    decision: Literal["CONFIRMED_RESOLVED", "DISPUTED"]
    notes: str | None = Field(None, max_length=1000, description="What the citizen found.")
    checked_myself: Literal[True] = Field(
        description="The citizen ticked 'I checked the place myself'. The AI never decides."
    )


class ReopenRequest(BaseModel):
    notes: str | None = Field(None, max_length=1000)
    checked_myself: Literal[True]


class ResolutionReviewRead(BaseModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    followup_evidence: EvidenceRead
    original_evidence: EvidenceRead | None
    ai_status: Literal["SUCCEEDED", "FAILED"]
    ai_error_code: str | None
    is_mock: bool
    assessment: dict[str, Any] | None  # ResolutionAssessment fields (see ai/schemas.py)
    cautions: list[str]  # plain-language warnings from resolutions/rules.py
    decision: Literal["PENDING", "CONFIRMED_RESOLVED", "DISPUTED", "SUPERSEDED"]
    citizen_notes: str | None
    decided_at: datetime | None
    created_at: datetime

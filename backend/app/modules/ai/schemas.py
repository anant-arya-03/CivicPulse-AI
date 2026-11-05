"""Structured AI outputs (what the model must return) and the API's response models.

The model outputs are plain Pydantic models. The SDK turns them into a JSON schema for the
model and validates the reply against them; our validators then sanitise every string.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.modules.ai.sanitize import sanitize_ai_text
from app.modules.complaints.constants import Category, Severity


def _clean_text(min_length: int, max_length: int) -> AfterValidator:
    def validate(value: str) -> str:
        cleaned = sanitize_ai_text(value, max_length=max_length)
        if len(cleaned) < min_length:
            raise ValueError(f"must be at least {min_length} characters after cleaning")
        return cleaned

    return AfterValidator(validate)


def _clean_list(max_items: int, max_length: int) -> AfterValidator:
    def validate(items: list[str]) -> list[str]:
        cleaned = [sanitize_ai_text(item, max_length=max_length) for item in items]
        return [item for item in cleaned if item][:max_items]

    return AfterValidator(validate)


# ── What the Vision agent must return (prompt vision.v1) ────────────────────


class VisionAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_civic_issue: bool = Field(
        description="True only if the photo clearly shows a public infrastructure problem."
    )
    category: Category
    category_confidence: Literal["HIGH", "MEDIUM", "LOW"]
    suggested_title: Annotated[
        str,
        _clean_text(5, 120),
        Field(description="A short neutral title, at most 120 characters."),
    ]
    suggested_description: Annotated[
        str,
        _clean_text(10, 800),
        Field(description="2-3 factual sentences about what is visible, at most 800 characters."),
    ]
    severity: Severity = Field(description="Conservative. UNKNOWN when unsure.")
    observations: Annotated[
        list[str],
        _clean_list(6, 200),
        Field(description="Up to 6 short visible facts, each at most 200 characters."),
    ]
    uncertainties: Annotated[
        list[str],
        _clean_list(6, 200),
        Field(description="Up to 6 things that cannot be judged from the photo."),
    ]
    warnings: Annotated[
        list[str],
        _clean_list(4, 200),
        Field(description="Up to 4 notes for the reporter, e.g. people's faces are visible."),
    ]


# ── What the Complaint Letter agent must return (prompt complaint_letter.v1) ─
# Only the wording. Facts (reference, address, dates, photo count) are added by
# letter_template.py so the model cannot change or invent them.


class ComplaintLetterProse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: Annotated[
        str, _clean_text(10, 150), Field(description="Email subject line, at most 150 characters.")
    ]
    issue_summary: Annotated[
        str,
        _clean_text(20, 1200),
        Field(
            description="2-4 formal sentences describing the problem, using only the facts given."
        ),
    ]
    requested_action: Annotated[
        str,
        _clean_text(10, 500),
        Field(
            description="1-2 polite sentences saying what the citizen asks the department to do."
        ),
    ]


# ── What the Monitoring agent must return (prompts reply_classification.v1, followup_letter.v1)


class ReplyClassification(BaseModel):
    """The AI's reading of a department's reply. Only a suggestion: fixed rules decide the
    effect (monitoring/rules.py), and a reference number is kept only if it literally appears
    in the reply."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal[
        "ACKNOWLEDGMENT",
        "IN_PROGRESS",
        "RESOLVED_CLAIM",
        "REQUEST_FOR_INFO",
        "REJECTION",
        "UNRELATED",
    ] = Field(description="What the reply means for the complaint.")
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    reference_number: str | None = Field(
        None,
        max_length=60,
        description="The department's reference number for the complaint, copied exactly, "
        "or null if the reply contains none.",
    )
    summary: Annotated[
        str,
        _clean_text(5, 300),
        Field(description="One or two plain sentences: what the department said."),
    ]


class FollowupProse(BaseModel):
    """The wording of a polite reminder. Facts (dates, references, place) come from
    followup_template.py, never from the model."""

    model_config = ConfigDict(extra="ignore")

    opening: Annotated[
        str,
        _clean_text(20, 800),
        Field(description="1-3 polite sentences saying the citizen is following up."),
    ]
    requested_action: Annotated[
        str,
        _clean_text(10, 400),
        Field(description="1 polite sentence asking for an update or action."),
    ]


# ── What the Resolution agent must return (prompt resolution.v1) ────────────


class ResolutionAssessment(BaseModel):
    """The AI's before/after comparison. Only advice: the citizen alone decides whether the
    problem is fixed. "APPEARS_" on purpose: a photo can't prove a repair."""

    model_config = ConfigDict(extra="ignore")

    assessment: Literal[
        "APPEARS_RESOLVED", "PARTIALLY_RESOLVED", "NOT_RESOLVED", "CANNOT_DETERMINE"
    ]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    same_location_likely: Literal["YES", "NO", "UNSURE"] = Field(
        description="Do both photos appear to show the same place?"
    )
    visible_changes: Annotated[
        list[str],
        _clean_list(6, 200),
        Field(description="Up to 6 visible differences between the photos."),
    ]
    remaining_problems: Annotated[
        list[str],
        _clean_list(6, 200),
        Field(description="Up to 6 problems still visible in the second photo."),
    ]
    uncertainties: Annotated[
        list[str],
        _clean_list(6, 200),
        Field(description="Up to 6 things that cannot be judged from these photos."),
    ]
    summary: Annotated[
        str,
        _clean_text(10, 400),
        Field(description="1-2 plain sentences. Say 'appears', never 'is definitely'."),
    ]


# ── API models ──────────────────────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    evidence_id: uuid.UUID | None = Field(
        None, description="Which photo to analyse. Defaults to the complaint's first photo."
    )


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    analysis_type: str
    status: Literal["SUCCEEDED", "FAILED"]
    provider: str
    model: str
    prompt_version: str
    is_mock: bool
    evidence_id: uuid.UUID | None
    result: VisionAnalysis | None = None
    error_code: str | None
    created_at: datetime


class ComplaintDraftRequest(BaseModel):
    mode: Literal["ai", "template"] = Field(
        "ai", description="'template' builds the letter without AI (the manual fallback)."
    )
    replace_existing: bool = Field(
        False, description="Must be true to replace a letter the citizen already has."
    )


class ComplaintDraftResponse(BaseModel):
    draft_subject: str
    draft_body: str
    source: Literal["ai", "template"]
    is_mock: bool
    analysis_id: uuid.UUID | None


def analysis_to_read(analysis: Any) -> AnalysisRead:
    """Build the API view, parsing the stored JSON back into a VisionAnalysis."""
    read = AnalysisRead.model_validate(analysis)
    if analysis.status == "SUCCEEDED" and analysis.analysis_type == "VISION":
        read.result = VisionAnalysis.model_validate(analysis.structured_result)
    return read

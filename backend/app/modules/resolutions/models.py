"""Resolution reviews: the audited record of each check of a reported repair."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base

DECISIONS = ("PENDING", "CONFIRMED_RESOLVED", "DISPUTED", "SUPERSEDED")


class ResolutionReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One "after" photo, the AI's comparison with the "before" photo (advice only), and the
    citizen's decision. Rows are never deleted or rewritten after the decision (audit trail).
    """

    __tablename__ = "resolution_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN (" + ", ".join(f"'{d}'" for d in DECISIONS) + ")", name="decision_valid"
        ),
        CheckConstraint("ai_status IN ('SUCCEEDED', 'FAILED')", name="ai_status_valid"),
        # A decision always records when it was made.
        CheckConstraint(
            "decision IN ('PENDING', 'SUPERSEDED') OR decided_at IS NOT NULL",
            name="decided_has_time",
        ),
        # At most one review per complaint waits for a decision.
        Index(
            "uq_resolution_reviews_one_pending",
            "complaint_id",
            unique=True,
            postgresql_where=text("decision = 'PENDING'"),
        ),
    )

    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # One review per "after" photo.
    followup_evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    original_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="SET NULL")
    )
    ai_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_analyses.id", ondelete="SET NULL")
    )
    ai_status: Mapped[str] = mapped_column(String(20), nullable=False)
    ai_error_code: Mapped[str | None] = mapped_column(String(40))
    ai_assessment: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # validated snapshot
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    citizen_notes: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

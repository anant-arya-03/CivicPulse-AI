import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import UUIDPrimaryKeyMixin
from app.common.time import utc_now
from app.core.database import Base


class AIAnalysis(UUIDPrimaryKeyMixin, Base):
    """One row per AI call, successful or not. Records exactly which provider, model, and prompt
    version produced a result, so results can be explained and compared later."""

    __tablename__ = "ai_analyses"
    __table_args__ = (
        CheckConstraint(
            "analysis_type IN "
            "('VISION', 'COMPLAINT_DRAFT', 'REPLY_CLASSIFICATION', 'FOLLOWUP_DRAFT', 'RESOLUTION')",
            name="analysis_type_valid",
        ),
        CheckConstraint("status IN ('SUCCEEDED', 'FAILED')", name="status_valid"),
        Index(
            "ix_ai_analyses_complaint_type_created", "complaint_id", "analysis_type", "created_at"
        ),
    )

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    analysis_type: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="SET NULL")
    )
    # The reply that was classified (REPLY_CLASSIFICATION).
    communication_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("communications.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    structured_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(String(500))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

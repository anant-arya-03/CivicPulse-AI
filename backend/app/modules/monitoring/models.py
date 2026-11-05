"""Database-backed scheduled actions: the reliable "check back later" list for the worker."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base
from app.modules.monitoring.constants import ActionStatus, ActionType

_STATUSES = ", ".join(f"'{s.value}'" for s in ActionStatus)
_TYPES = ", ".join(f"'{t.value}'" for t in ActionType)


class ScheduledAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One thing the worker should do at (or after) `scheduled_at`.

    Reliability rules:
    - `idempotency_key` is UNIQUE, so the same check can never be scheduled twice.
    - Workers claim rows with SELECT ... FOR UPDATE SKIP LOCKED, so two workers never run the
      same action, and a failing action is retried a limited number of times.
    - An action never sends anything. At most it drafts a reminder for the citizen to approve.
    """

    __tablename__ = "scheduled_actions"
    __table_args__ = (
        CheckConstraint(f"action_type IN ({_TYPES})", name="action_type_valid"),
        CheckConstraint(f"execution_status IN ({_STATUSES})", name="execution_status_valid"),
        # The worker's query: due PENDING actions, oldest first.
        Index(
            "ix_scheduled_actions_pending_due",
            "scheduled_at",
            postgresql_where=text("execution_status = 'PENDING'"),
        ),
        Index("ix_scheduled_actions_complaint", "complaint_id", "created_at"),
    )

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    execution_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ActionStatus.PENDING.value
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    # Why it was scheduled: {"trigger": ..., "after_communication_id": ..., "basis": ...}
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    outcome: Mapped[str | None] = mapped_column(String(300))  # what happened, in plain words
    last_error: Mapped[str | None] = mapped_column(String(500))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base

DELIVERY_STATUSES = (
    "DRAFT",  # a suggested reminder the citizen hasn't approved yet (follow-ups only)
    "APPROVED",
    "SENDING",
    "SENT",
    "SIMULATED_SENT",
    "FAILED",
    "SUPERSEDED",
    "CANCELLED",  # a reminder that is no longer needed or that the citizen chose not to send
    "RECEIVED",  # an incoming reply
)
REPLY_KINDS = (
    "ACKNOWLEDGMENT",
    "IN_PROGRESS",
    "RESOLVED_CLAIM",
    "REQUEST_FOR_INFO",
    "REJECTION",
    "UNRELATED",
)


class Communication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One message to or from a department. Outgoing messages are snapshots of exactly what the
    citizen approved; they are never edited afterwards (a reminder can be edited while it is
    still a DRAFT). Incoming replies are untrusted text: stored and shown as plain text only."""

    __tablename__ = "communications"
    __table_args__ = (
        CheckConstraint("direction IN ('OUTBOUND', 'INBOUND')", name="direction_valid"),
        CheckConstraint(
            "communication_type IN ('COMPLAINT', 'FOLLOW_UP', 'REPLY')", name="type_valid"
        ),
        CheckConstraint(
            "delivery_status IN (" + ", ".join(f"'{s}'" for s in DELIVERY_STATUSES) + ")",
            name="delivery_status_valid",
        ),
        # A simulated message can never be recorded as really delivered.
        CheckConstraint(
            "NOT (is_simulated AND delivery_status = 'SENT')", name="simulated_never_sent"
        ),
        CheckConstraint(
            "reply_kind IS NULL OR reply_kind IN ("
            + ", ".join(f"'{k}'" for k in REPLY_KINDS)
            + ")",
            name="reply_kind_valid",
        ),
        Index("ix_communications_complaint_created", "complaint_id", "created_at"),
    )

    # Insertion order. Windows' clock can give two rows the same created_at, so order by this.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    authority_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorities.id", ondelete="SET NULL")
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    communication_type: Mapped[str] = mapped_column(String(20), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="EMAIL")
    recipient: Mapped[str | None] = mapped_column(String(254))
    sender: Mapped[str | None] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    delivery_status: Mapped[str] = mapped_column(String(30), nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    # Unique: the same message can never be created (and so never sent) twice.
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    # SHA-256 of recipient + subject + body + attachments, as approved by the citizen.
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    approval_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Follow-ups: 1 for the first reminder, 2 for the second, ...
    followup_number: Mapped[int | None] = mapped_column(Integer)
    # Replies: what the reply means (see monitoring/constants.ReplyKind), and who decided it.
    # NULL kind on a reply = the citizen still needs to tell us (AI unavailable or unsure).
    reply_kind: Mapped[str | None] = mapped_column(String(30))
    reply_kind_source: Mapped[str | None] = mapped_column(String(20))  # AI | CITIZEN
    reply_summary: Mapped[str | None] = mapped_column(String(500))  # sanitised AI summary
    reference_number: Mapped[str | None] = mapped_column(String(40))  # found in this reply

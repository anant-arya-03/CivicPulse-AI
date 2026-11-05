import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    Sequence,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.common.time import utc_now
from app.core.database import Base
from app.modules.complaints.constants import ComplaintStatus

if TYPE_CHECKING:  # only for type hints; avoids a circular import at runtime
    from app.modules.authorities.models import Authority
    from app.modules.evidence.models import Evidence

# Numbers the human-friendly references (CP-2026-000001, CP-2026-000002, ...).
complaint_reference_seq = Sequence("complaint_reference_seq", metadata=Base.metadata)

_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in ComplaintStatus)


class Complaint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="status_valid"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude_range"
        ),
        Index("ix_complaints_user_created", "user_id", "created_at"),
        Index("ix_complaints_user_status", "user_id", "status"),
    )

    public_reference: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(40), index=True)
    severity: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default=ComplaintStatus.DRAFT.value
    )

    # Location: always provided by the citizen, never guessed from the photo.
    address_line: Mapped[str | None] = mapped_column(String(255))
    locality: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(2))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    location_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # The formal complaint letter, drafted by AI or from the template and edited by the citizen.
    # Milestone 4 turns the approved text into the outgoing message.
    draft_subject: Mapped[str | None] = mapped_column(String(200))
    draft_body: Mapped[str | None] = mapped_column(Text)

    # Filled in by later milestones (department, replies, submission).
    authority_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorities.id", ondelete="SET NULL"), index=True
    )
    authority_reference_number: Mapped[str | None] = mapped_column(String(100))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    authority: Mapped["Authority | None"] = relationship()
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="complaint",
        order_by="Evidence.created_at",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["ComplaintEvent"]] = relationship(
        back_populates="complaint",
        order_by="(ComplaintEvent.created_at, ComplaintEvent.seq)",
        cascade="all, delete-orphan",
    )


class ComplaintEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only audit trail. Powers the timeline and the activity feed."""

    __tablename__ = "complaint_events"
    __table_args__ = (
        Index("ix_complaint_events_complaint_created", "complaint_id", "created_at", "seq"),
    )

    # Increases with every insert. Breaks ties when several events share the same timestamp
    # (e.g. two events recorded in one request), so the timeline order is always correct.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    actor: Mapped[str] = mapped_column(String(20), nullable=False)
    # "metadata" is reserved by SQLAlchemy, so the Python attribute is `details`.
    details: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    complaint: Mapped[Complaint] = relationship(back_populates="events")

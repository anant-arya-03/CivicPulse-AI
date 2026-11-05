import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import UUIDPrimaryKeyMixin
from app.common.time import utc_now
from app.core.database import Base
from app.modules.complaints.models import Complaint


class Evidence(UUIDPrimaryKeyMixin, Base):
    """A photo attached to a complaint. The file itself lives in StorageService."""

    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("evidence_type IN ('ORIGINAL', 'FOLLOWUP')", name="evidence_type_valid"),
        # The same photo can't be attached to the same complaint twice.
        UniqueConstraint("complaint_id", "checksum", name="uq_evidence_complaint_checksum"),
    )

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    complaint: Mapped[Complaint] = relationship(back_populates="evidence")

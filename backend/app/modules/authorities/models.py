import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.dialects.postgresql import ARRAY  # supports contains() / the @> operator
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class Authority(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A government department that handles certain civic issues in a certain area.

    The directory never contains invented contacts. A real record (is_demo = false) must say
    where its details come from (source_url) and when a person last checked them (verified_at);
    the database refuses it otherwise. Fictional demo records are flagged is_demo = true and use
    unreachable .example addresses.
    """

    __tablename__ = "authorities"
    __table_args__ = (
        CheckConstraint(
            "is_demo OR (source_url IS NOT NULL AND verified_at IS NOT NULL)",
            name="real_records_are_source_backed",
        ),
        CheckConstraint(
            "jurisdiction_level IN ('WARD', 'CITY', 'DISTRICT', 'STATE', 'NATIONAL')",
            name="jurisdiction_level_valid",
        ),
        UniqueConstraint("name", "city", "state", "country", name="uq_authorities_name_place"),
        Index(
            "ix_authorities_supported_categories", "supported_categories", postgresql_using="gin"
        ),
        Index("ix_authorities_city", "city"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(200), nullable=False)  # display text
    jurisdiction_level: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    # Category values (see complaints/constants.py). Empty = escalation-only office.
    supported_categories: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list, server_default="{}"
    )
    official_email: Mapped[str | None] = mapped_column(String(254))
    official_phone: Mapped[str | None] = mapped_column(String(40))
    website_url: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(500))  # where the details were found
    verified_at: Mapped[date | None] = mapped_column(Date)  # when a person last checked them
    verification_notes: Mapped[str | None] = mapped_column(Text)
    service_timeline_days: Mapped[int | None] = mapped_column(Integer)  # only if a source says so
    parent_authority_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorities.id", ondelete="SET NULL")
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

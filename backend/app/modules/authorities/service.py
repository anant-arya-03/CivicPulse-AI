"""Authority directory: search, matching a complaint to departments, choosing one, and loading
records (fictional demo seed, or verified real records through the importer)."""

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, NotFoundError
from app.modules.authorities.demo_data import DEMO_AUTHORITIES
from app.modules.authorities.matcher import MatchResult, match_authorities
from app.modules.authorities.models import Authority
from app.modules.authorities.schemas import AuthorityImport
from app.modules.complaints import service as complaint_service
from app.modules.complaints.constants import CATEGORY_LABELS, Category, EventType
from app.modules.complaints.models import Complaint
from app.modules.users.models import User


def list_authorities(
    db: Session, *, q: str | None = None, category: Category | None = None, city: str | None = None
) -> list[Authority]:
    query = select(Authority).where(Authority.active.is_(True))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(Authority.name.ilike(pattern), Authority.jurisdiction.ilike(pattern))
        )
    if category:
        query = query.where(Authority.supported_categories.contains([category.value]))
    if city:
        query = query.where(or_(Authority.city.ilike(city.strip()), Authority.city.is_(None)))
    return list(db.scalars(query.order_by(Authority.name).limit(50)).all())


def get_authority(db: Session, authority_id: uuid.UUID) -> Authority:
    authority = db.get(Authority, authority_id)
    if authority is None or not authority.active:
        raise NotFoundError("Department not found.")
    return authority


def _require_matchable(complaint: Complaint) -> Category:
    if not complaint.category:
        raise BusinessRuleError("Choose the type of issue first.")
    if not complaint.city:
        raise BusinessRuleError("Add the city where the problem is first.")
    return Category(complaint.category)


def matches_for_complaint(
    db: Session, user: User, complaint_id: uuid.UUID
) -> tuple[Complaint, MatchResult]:
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    category = _require_matchable(complaint)
    candidates = db.scalars(
        select(Authority).where(
            Authority.active.is_(True), Authority.supported_categories.contains([category.value])
        )
    ).all()
    result = match_authorities(
        candidates,
        category=category.value,
        city=complaint.city,
        state=complaint.state,
        country=complaint.country,
        category_label=CATEGORY_LABELS[category],
    )
    return complaint, result


def select_authority(
    db: Session, user: User, complaint_id: uuid.UUID, authority_id: uuid.UUID
) -> Complaint:
    complaint = complaint_service.get_editable_complaint(db, user, complaint_id)
    category = _require_matchable(complaint)
    authority = get_authority(db, authority_id)
    if category.value not in authority.supported_categories:
        raise BusinessRuleError(
            f"{authority.name} doesn't handle {CATEGORY_LABELS[category].lower()} issues."
        )
    if not authority.official_email:
        raise BusinessRuleError(f"{authority.name} has no public email address on record.")

    if complaint.authority_id != authority.id:
        complaint.authority_id = authority.id
        complaint_service.withdraw_approval(db, complaint, "the department was changed")
        demo = " (demo directory entry)" if authority.is_demo else ""
        complaint_service.record_event(
            db,
            complaint,
            EventType.AUTHORITY_SELECTED,
            f"Department selected: {authority.name}{demo}.",
            details={"authority_id": str(authority.id)},
        )
        db.commit()
    return complaint_service.get_owned_complaint(db, user, complaint.id)


# ── Loading records ─────────────────────────────────────────────────────────


def _upsert(db: Session, record: dict[str, Any]) -> Authority:
    existing = db.scalar(
        select(Authority).where(
            Authority.name == record["name"],
            Authority.city.is_(None)
            if record.get("city") is None
            else Authority.city == record["city"],
            Authority.state.is_(None)
            if record.get("state") is None
            else Authority.state == record["state"],
            Authority.country == record["country"],
        )
    )
    authority = existing or Authority()
    for key, value in record.items():
        setattr(authority, key, value)
    if existing is None:
        db.add(authority)
    db.flush()
    return authority


def _link_parents(db: Session, records: Iterable[tuple[Authority, str | None]]) -> None:
    for authority, parent_name in records:
        if not parent_name:
            continue
        parent = db.scalar(
            select(Authority).where(
                Authority.name == parent_name, Authority.country == authority.country
            )
        )
        if parent is None:
            raise BusinessRuleError(f"Parent department not found: {parent_name}")
        authority.parent_authority_id = parent.id


def seed_demo_authorities(db: Session) -> int:
    """Insert or update the fictional demo directory. Safe to run repeatedly."""
    linked = []
    for raw in DEMO_AUTHORITIES:
        record = {k: v for k, v in raw.items() if k != "parent"}
        linked.append((_upsert(db, record), raw.get("parent")))
    _link_parents(db, linked)
    db.commit()
    return len(linked)


def import_authorities(db: Session, items: list[AuthorityImport]) -> int:
    """Insert or update verified REAL records (validated by AuthorityImport)."""
    linked = []
    for item in items:
        record = item.model_dump(mode="json", exclude={"parent_name"})
        record["verified_at"] = item.verified_at
        record["supported_categories"] = [c.value for c in item.supported_categories]
        record["is_demo"] = False
        linked.append((_upsert(db, record), item.parent_name))
    _link_parents(db, linked)
    db.commit()
    return len(linked)

"""Department access to approved complaints in the local simulation."""

from hmac import compare_digest
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import InvalidTransitionError, NotFoundError, UnauthenticatedError
from app.modules.authorities.models import Authority
from app.modules.communications.models import Communication
from app.modules.complaints.constants import MONITORED_STATUSES, ComplaintStatus
from app.modules.complaints.models import Complaint
from app.modules.department_portal.schemas import DepartmentReport, ReportUpdate
from app.modules.evidence.models import Evidence
from app.modules.monitoring.constants import ReplyKind
from app.modules.monitoring.service import receive_reply


def authenticate(db: Session, access_code: str | None) -> Authority:
    settings = get_settings()
    if (
        settings.is_production
        or not settings.enable_simulation
        or not settings.department_access_code
    ):
        raise NotFoundError("Department portal is unavailable.")
    expected = settings.department_access_code.get_secret_value().encode()
    if access_code is None or not compare_digest(access_code.encode(), expected):
        raise UnauthenticatedError("Enter the department access code.")
    authority = db.scalar(
        select(Authority).where(
            Authority.official_email == settings.department_authority_email,
            Authority.is_demo.is_(True),
            Authority.active.is_(True),
        )
    )
    if authority is None:
        raise NotFoundError("The configured demo department is unavailable.")
    return authority


def _delivered_reports(authority: Authority):
    return (
        select(Complaint, Communication)
        .join(Communication, Complaint.id == Communication.complaint_id)
        .where(
            Complaint.authority_id == authority.id,
            Communication.authority_id == authority.id,
            Communication.direction == "OUTBOUND",
            Communication.communication_type == "COMPLAINT",
            Communication.delivery_status == "SIMULATED_SENT",
            Communication.is_simulated.is_(True),
        )
        .order_by(Communication.seq.desc())
    )


def _report(complaint: Complaint, sent: Communication) -> DepartmentReport:
    return DepartmentReport(
        id=complaint.id,
        reference=complaint.public_reference,
        status=ComplaintStatus(complaint.status),
        subject=sent.subject,
        body=sent.body,
        received_at=sent.sent_at,
        attachment_ids=[UUID(item["evidence_id"]) for item in sent.attachments],
    )


def list_reports(db: Session, authority: Authority) -> list[DepartmentReport]:
    return [
        _report(complaint, sent) for complaint, sent in db.execute(_delivered_reports(authority))
    ]


def get_attachment(
    db: Session, authority: Authority, complaint_id: UUID, evidence_id: UUID
) -> Evidence:
    deliveries = db.execute(_delivered_reports(authority).where(Complaint.id == complaint_id))
    if not any(
        item.get("evidence_id") == str(evidence_id)
        for _, sent in deliveries
        for item in sent.attachments
    ):
        raise NotFoundError("Photo not found.")
    evidence = db.get(Evidence, evidence_id)
    if evidence is None or evidence.complaint_id != complaint_id:
        raise NotFoundError("Photo not found.")
    return evidence


def update_report(
    db: Session, authority: Authority, complaint_id: UUID, update: ReportUpdate
) -> DepartmentReport:
    row = db.execute(
        _delivered_reports(authority)
        .where(Complaint.id == complaint_id)
        .limit(1)
        .with_for_update(of=Complaint)
    ).first()
    if row is None:
        raise NotFoundError("Report not found.")
    complaint, sent = row
    status = ComplaintStatus(complaint.status)
    if update == "repair_complete":
        target = ComplaintStatus.RESOLVED_PENDING_VERIFICATION
        kind = ReplyKind.RESOLVED_CLAIM
        subject = "Repair complete"
        body = "The department reports that the repair is complete. Please check the site."
    else:
        target = ComplaintStatus.IN_PROGRESS
        kind = ReplyKind.IN_PROGRESS
        subject = "Work started"
        body = "The department has started work on this report."
    if status == target:
        return _report(complaint, sent)
    if status not in MONITORED_STATUSES:
        raise InvalidTransitionError("This report is no longer awaiting department action.")
    receive_reply(
        db, None, complaint, subject=subject, body=body, is_simulated=True, reported_kind=kind
    )
    db.commit()
    return _report(complaint, sent)

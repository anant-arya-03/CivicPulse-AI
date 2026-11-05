"""Response monitoring and smart follow-ups.

Guarantees (each one is tested):
1. Nothing is ever sent from here. The worker only DRAFTS reminders; the citizen edits,
   approves (content hash) and sends each one through communications.service.
2. No spam: at most FOLLOWUP_MAX_COUNT reminders per complaint; never while another reminder is
   waiting; never after the department replied (until a new deadline passes); never once the
   complaint is resolved, closed or withdrawn. Deadlines follow the department's listed
   response time when the directory has one.
3. Replies are untrusted text. The AI only suggests what a reply means; fixed rules
   (rules.reply_effect) decide the effect, and the strongest one, "the department says it's
   fixed", still needs the citizen. If the AI is unavailable or unsure, the citizen decides.
   A reference number is stored only if it appears word-for-word in the reply.
4. Escalation contacts come only from active directory records, and nobody is contacted for
   the citizen.
5. Scheduled actions are reliable: unique keys (never scheduled twice), row locks with
   SKIP LOCKED (never run twice at once), limited retries, and recovery of stuck runs.
"""

import logging
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.integrations.ai_providers.base import AIProvider
from app.integrations.email_providers.base import EmailProvider
from app.modules.ai import service as ai_service
from app.modules.ai.followup_template import (
    build_followup_facts,
    render_followup,
    render_not_fixed_notice,
)
from app.modules.authorities.models import Authority
from app.modules.authorities.schemas import AuthorityRead
from app.modules.communications.hashing import message_sha256
from app.modules.communications.models import Communication
from app.modules.communications.schemas import CommunicationRead
from app.modules.complaints import service as complaint_service
from app.modules.complaints.constants import (
    MONITORED_STATUSES,
    Actor,
    ComplaintStatus,
    EventType,
)
from app.modules.complaints.models import Complaint, ComplaintEvent
from app.modules.complaints.schemas import AttentionItem
from app.modules.monitoring import rules
from app.modules.monitoring.constants import (
    REPLY_KIND_LABELS,
    ActionStatus,
    ActionType,
    CheckTrigger,
    ReplyKind,
    ReplyKindSource,
)
from app.modules.monitoring.models import ScheduledAction
from app.modules.monitoring.schemas import EscalationRead, MonitoringRead
from app.modules.monitoring.simulation import reply_scenarios
from app.modules.users.models import User

logger = logging.getLogger(__name__)

_OPEN_FOLLOWUP = ("DRAFT", "APPROVED", "FAILED", "SENDING")  # a reminder not finished yet
_CANCELLABLE_FOLLOWUP = ("DRAFT", "APPROVED", "FAILED")
_SENT = ("SENT", "SIMULATED_SENT")
_STUCK_RUNNING_AFTER = timedelta(minutes=15)
_MAX_INBOUND_CHARS = 20_000
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# ── Reading the message history ─────────────────────────────────────────────


def _messages(db: Session, complaint: Complaint) -> list[Communication]:
    return list(
        db.scalars(
            select(Communication)
            .where(Communication.complaint_id == complaint.id)
            .order_by(Communication.seq)
        ).all()
    )


def _followups(db: Session, complaint: Complaint) -> list[Communication]:
    return [m for m in _messages(db, complaint) if m.communication_type == "FOLLOW_UP"]


def _replies(db: Session, complaint: Complaint) -> list[Communication]:
    return [m for m in _messages(db, complaint) if m.direction == "INBOUND"]


def sent_followup_count(db: Session, complaint: Complaint) -> int:
    """Numbered reminders sent. A "not fixed" notice (no number) doesn't count towards the limit:
    it is the citizen's answer to a claimed repair, not a repeated reminder."""
    return sum(
        1
        for m in _followups(db, complaint)
        if m.delivery_status in _SENT and m.followup_number is not None
    )


def open_followup(db: Session, complaint: Complaint) -> Communication | None:
    return next(
        (m for m in reversed(_followups(db, complaint)) if m.delivery_status in _OPEN_FOLLOWUP),
        None,
    )


def _unreviewed_replies(db: Session, complaint: Complaint) -> list[Communication]:
    return [m for m in _replies(db, complaint) if m.reply_kind is None]


def _relevant_reply_after(db: Session, complaint: Complaint, seq: int) -> bool:
    return any(
        m.seq > seq and m.reply_kind not in (None, ReplyKind.UNRELATED.value)
        for m in _replies(db, complaint)
    )


def _pending_check(db: Session, complaint: Complaint) -> ScheduledAction | None:
    return db.scalar(
        select(ScheduledAction)
        .where(
            ScheduledAction.complaint_id == complaint.id,
            ScheduledAction.execution_status == ActionStatus.PENDING.value,
        )
        .order_by(ScheduledAction.scheduled_at)
        .limit(1)
    )


# ── Scheduling and stopping ─────────────────────────────────────────────────


def schedule_check(
    db: Session,
    complaint: Complaint,
    trigger: CheckTrigger,
    *,
    at: datetime,
    after: Communication,
) -> ScheduledAction | None:
    """Schedule "has the department answered?" for the deadline that starts with `after`.
    Idempotent: one check per message, whatever happens (the key is UNIQUE). The caller commits.
    """
    if ComplaintStatus(complaint.status) not in MONITORED_STATUSES:
        return None
    key = f"followup_check:{complaint.id}:after:{after.id}"
    existing = db.scalar(select(ScheduledAction).where(ScheduledAction.idempotency_key == key))
    if existing is not None:
        return existing

    settings = get_settings()
    authority = complaint.authority
    deadline = rules.next_check(
        trigger,
        at=at,
        submitted_at=complaint.submitted_at,
        service_timeline_days=authority.service_timeline_days if authority else None,
        first_after_days=settings.followup_first_after_days,
        interval_days=settings.followup_interval_days,
    )
    action = ScheduledAction(
        complaint_id=complaint.id,
        action_type=ActionType.FOLLOWUP_CHECK.value,
        scheduled_at=deadline.due_at,
        execution_status=ActionStatus.PENDING.value,
        idempotency_key=key,
        payload={
            "trigger": trigger.value,
            "after_communication_id": str(after.id),
            "basis": deadline.basis,
            "official": deadline.official,
        },
    )
    db.add(action)
    db.flush()
    return action


def stop_monitoring(db: Session, complaint: Complaint, reason: str) -> None:
    """Cancel pending checks and unsent reminder drafts. The caller commits."""
    actions = db.scalars(
        select(ScheduledAction).where(
            ScheduledAction.complaint_id == complaint.id,
            ScheduledAction.execution_status == ActionStatus.PENDING.value,
        )
    ).all()
    for action in actions:
        action.execution_status = ActionStatus.CANCELLED.value
        action.outcome = f"Cancelled because {reason}."
    drafts = [m for m in _followups(db, complaint) if m.delivery_status in _CANCELLABLE_FOLLOWUP]
    for draft in drafts:
        draft.delivery_status = "CANCELLED"
    if actions or drafts:
        complaint_service.record_event(
            db,
            complaint,
            EventType.FOLLOWUPS_STOPPED,
            f"Reminders stopped because {reason}."
            + (" The unsent reminder was cancelled." if drafts else ""),
            actor=Actor.SYSTEM,
            details={"cancelled_checks": len(actions), "cancelled_reminders": len(drafts)},
        )


# ── Incoming replies ────────────────────────────────────────────────────────


def _clean_inbound(text: str) -> str:
    """Plain text only, length-limited. It is always displayed as text, never as HTML."""
    cleaned = _CONTROL_CHARS.sub("", text.replace("\r\n", "\n"))
    return cleaned[:_MAX_INBOUND_CHARS].strip()


def receive_reply(
    db: Session,
    ai: AIProvider,
    complaint: Complaint,
    *,
    subject: str,
    body: str,
    is_simulated: bool,
) -> Communication:
    """Store a department's reply, let the AI suggest its meaning, and apply the fixed rules
    if the AI is confident. Otherwise the citizen is asked. The caller commits."""
    authority = complaint.authority
    now = utc_now()
    text = _clean_inbound(body)
    reply = Communication(
        complaint_id=complaint.id,
        authority_id=authority.id if authority else None,
        direction="INBOUND",
        communication_type="REPLY",
        channel="EMAIL",
        sender=authority.official_email if authority else None,
        recipient=get_settings().email_from_address,
        subject=_clean_inbound(subject)[:255] or "(no subject)",
        body=text,
        attachments=[],
        delivery_status="RECEIVED",
        is_simulated=is_simulated,
        provider="simulation" if is_simulated else None,
        received_at=now,
    )
    db.add(reply)
    db.flush()
    complaint.last_response_at = now
    name = authority.name if authority else "the department"
    complaint_service.record_event(
        db,
        complaint,
        EventType.REPLY_RECEIVED,
        f"Simulated reply received from {name}."
        if is_simulated
        else f"Reply received from {name}.",
        actor=Actor.AUTHORITY,
        details={"communication_id": str(reply.id), "is_simulated": is_simulated},
    )

    result = ai_service.classify_reply(db, ai, complaint, reply)
    own = complaint.public_reference
    suggested = result.output.reference_number if result else None
    reply.reference_number = rules.accept_reference(
        suggested, text, own_reference=own
    ) or rules.find_reference_number(text, own_reference=own)
    if result is not None:
        reply.reply_summary = result.output.summary
        if rules.should_auto_apply(result.output.confidence):
            _apply_reply_kind(
                db,
                complaint,
                reply,
                ReplyKind(result.output.kind),
                source=ReplyKindSource.AI,
                is_mock=result.is_mock,
            )
    db.flush()
    return reply


def _apply_reply_kind(
    db: Session,
    complaint: Complaint,
    reply: Communication,
    kind: ReplyKind,
    *,
    source: ReplyKindSource,
    is_mock: bool = False,
) -> None:
    reply.reply_kind = kind.value
    reply.reply_kind_source = source.value
    who = "You" if source == ReplyKindSource.CITIZEN else ("Demo AI" if is_mock else "AI")
    complaint_service.record_event(
        db,
        complaint,
        EventType.REPLY_CLASSIFIED,
        f"{who} marked the reply as: {REPLY_KIND_LABELS[kind]}.",
        actor=Actor.CITIZEN if source == ReplyKindSource.CITIZEN else Actor.AI,
        details={"communication_id": str(reply.id), "kind": kind.value, "is_mock": is_mock},
    )

    # Only a reply about this complaint may set the department's reference number.
    if kind != ReplyKind.UNRELATED and reply.reference_number:
        if not complaint.authority_reference_number:
            complaint.authority_reference_number = reply.reference_number
            complaint_service.record_event(
                db,
                complaint,
                EventType.REFERENCE_NUMBER_RECORDED,
                f"Department reference number recorded: {reply.reference_number}.",
                actor=Actor.SYSTEM,
            )

    effect = rules.reply_effect(kind, ComplaintStatus(complaint.status))
    if effect.stop_reminders:
        stop_monitoring(db, complaint, effect.stop_reason)
    if effect.new_status is not None:
        if effect.new_status == ComplaintStatus.ACKNOWLEDGED:
            complaint.acknowledged_at = reply.received_at
        complaint_service.change_status(
            db,
            complaint,
            effect.new_status,
            event_type=EventType.STATUS_CHANGED,
            description=effect.status_note,
            actor=Actor.AUTHORITY,
        )
    received = reply.received_at or utc_now()
    if effect.keep_checking:
        schedule_check(db, complaint, CheckTrigger.PROGRESS_REPLY, at=received, after=reply)
    if kind == ReplyKind.UNRELATED and _pending_check(db, complaint) is None:
        # e.g. the check was skipped while this reply waited for review: keep waiting.
        schedule_check(db, complaint, CheckTrigger.UNRELATED_REPLY, at=received, after=reply)
    if effect.recommend_escalation:
        recommend_escalation(db, complaint, effect.stop_reason)


def classify_reply_manually(
    db: Session, user: User, communication_id: uuid.UUID, kind: ReplyKind
) -> Communication:
    """The manual path: the citizen says what a reply means (AI unavailable or unsure)."""
    reply = db.scalar(
        select(Communication)
        .join(Complaint, Communication.complaint_id == Complaint.id)
        .where(
            Communication.id == communication_id,
            Complaint.user_id == user.id,
            Communication.direction == "INBOUND",
        )
        .with_for_update(of=Communication)
    )
    if reply is None:
        raise NotFoundError("Reply not found.")
    if reply.reply_kind is not None:
        raise ConflictError("The meaning of this reply has already been recorded.")
    complaint = complaint_service.get_owned_complaint(db, user, reply.complaint_id)
    _apply_reply_kind(db, complaint, reply, kind, source=ReplyKindSource.CITIZEN)
    db.commit()
    return reply


# ── Escalation ──────────────────────────────────────────────────────────────


def escalation_contacts(db: Session, complaint: Complaint) -> list[Authority]:
    """Higher offices above the department, from the directory only (never guessed)."""
    contacts: list[Authority] = []
    seen: set[uuid.UUID] = set()
    current = complaint.authority
    for _ in range(3):  # department -> parent -> grandparent -> ...
        if current is None or current.parent_authority_id is None:
            break
        parent = db.get(Authority, current.parent_authority_id)
        if parent is None or parent.id in seen:
            break
        seen.add(parent.id)
        if parent.active and (parent.official_email or parent.official_phone):
            contacts.append(parent)
        current = parent
    return contacts


def recommend_escalation(db: Session, complaint: Complaint, reason: str) -> bool:
    """Record (once) that escalation is recommended. Nobody is contacted. The caller commits."""
    already = db.scalar(
        select(ComplaintEvent.id)
        .where(
            ComplaintEvent.complaint_id == complaint.id,
            ComplaintEvent.event_type == EventType.ESCALATION_RECOMMENDED.value,
        )
        .limit(1)
    )
    if already is not None:
        return False
    contacts = escalation_contacts(db, complaint)
    if contacts:
        names = ", ".join(c.name for c in contacts)
        text = (
            f"Escalation recommended because {reason}. Contact details for {names} from the "
            "directory are shown on this page. CivicPulse does not contact them for you."
        )
    else:
        text = (
            f"Escalation recommended because {reason}, but the directory lists no higher "
            "office for this department. CivicPulse never guesses contact details."
        )
    complaint_service.record_event(
        db,
        complaint,
        EventType.ESCALATION_RECOMMENDED,
        text,
        actor=Actor.SYSTEM,
        details={"reason": reason, "contact_ids": [str(c.id) for c in contacts]},
    )
    return True


# ── The worker ──────────────────────────────────────────────────────────────


def run_due_actions(
    db: Session,
    *,
    ai: AIProvider,
    email: EmailProvider,
    now: datetime | None = None,
    complaint_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[ScheduledAction]:
    """Run every action that is due at `now` (default: the real time), one at a time.

    `now` may be set in the future for demos ("what happens in 8 days?"). It only decides
    which actions are due; everything is still recorded with the real time.
    """
    now = now or utc_now()
    _release_stuck_actions(db)
    ran: list[ScheduledAction] = []
    while len(ran) < limit:
        action = _claim_next_due(db, now, complaint_id)
        if action is None:
            break
        _execute(db, action, ai=ai, email=email, now=now)
        ran.append(action)
    return ran


def _release_stuck_actions(db: Session) -> None:
    """A worker that crashed mid-run leaves its action RUNNING: make it runnable again."""
    stuck = db.scalars(
        select(ScheduledAction).where(
            ScheduledAction.execution_status == ActionStatus.RUNNING.value,
            ScheduledAction.updated_at < utc_now() - _STUCK_RUNNING_AFTER,
        )
    ).all()
    for action in stuck:
        action.execution_status = ActionStatus.PENDING.value
        action.last_error = "The previous run did not finish; retrying."
    if stuck:
        db.commit()


def _claim_next_due(
    db: Session, now: datetime, complaint_id: uuid.UUID | None
) -> ScheduledAction | None:
    query = (
        select(ScheduledAction)
        .where(
            ScheduledAction.execution_status == ActionStatus.PENDING.value,
            ScheduledAction.scheduled_at <= now,
        )
        .order_by(ScheduledAction.scheduled_at, ScheduledAction.created_at)
        .limit(1)
        # Another worker holding this row? Skip it rather than wait (and never run it twice).
        .with_for_update(skip_locked=True)
    )
    if complaint_id is not None:
        query = query.where(ScheduledAction.complaint_id == complaint_id)
    action = db.scalar(query)
    if action is None:
        return None
    action.execution_status = ActionStatus.RUNNING.value
    action.attempt_count += 1
    db.commit()
    return action


def _execute(
    db: Session, action: ScheduledAction, *, ai: AIProvider, email: EmailProvider, now: datetime
) -> None:
    try:
        status, outcome = _run_followup_check(db, action, ai=ai, email=email, now=now)
        action.execution_status = status.value
        action.outcome = outcome
        action.last_error = None
        action.executed_at = utc_now()
        db.commit()
    except Exception as error:  # one broken action must never stop the others
        db.rollback()
        logger.exception("Scheduled action %s failed", action.id)
        max_attempts = get_settings().scheduler_max_attempts
        action.last_error = f"{type(error).__name__}: {error}"[:500]
        if action.attempt_count >= max_attempts:
            action.execution_status = ActionStatus.FAILED.value
            action.executed_at = utc_now()
            action.outcome = f"Gave up after {action.attempt_count} attempts."
        else:
            action.execution_status = ActionStatus.PENDING.value
            # Wait longer after each failure: 5, 10, 20... minutes.
            action.scheduled_at = now + timedelta(minutes=5 * 2 ** (action.attempt_count - 1))
        db.commit()


def _run_followup_check(
    db: Session,
    action: ScheduledAction,
    *,
    ai: AIProvider,
    email: EmailProvider,
    now: datetime,
) -> tuple[ActionStatus, str]:
    """The deadline has passed. Re-check everything NOW (things change), then at most draft a
    reminder or recommend escalation. Never sends."""
    complaint = db.get(Complaint, action.complaint_id)
    assert complaint is not None  # the action is deleted with its complaint
    status = ComplaintStatus(complaint.status)
    if status not in MONITORED_STATUSES:
        return ActionStatus.SKIPPED, f"Not needed: the complaint is now {status.value}."

    after_id = action.payload.get("after_communication_id")
    after = db.get(Communication, uuid.UUID(after_id)) if after_id else None
    if _unreviewed_replies(db, complaint):
        return ActionStatus.SKIPPED, "Waiting for you to say what the department's reply means."
    if after is not None and _relevant_reply_after(db, complaint, after.seq):
        return ActionStatus.SKIPPED, "Not needed: the department replied."
    if open_followup(db, complaint) is not None:
        return ActionStatus.SKIPPED, "A reminder is already waiting for your approval."

    sent = sent_followup_count(db, complaint)
    if sent >= get_settings().followup_max_count:
        reason = (
            f"the department hasn't replied after {sent} reminder(s)"
            if sent
            else "the department hasn't replied"
        )
        recommend_escalation(db, complaint, reason)
        return ActionStatus.DONE, "No reply after the maximum number of reminders."

    authority = complaint.authority
    if authority is None or not authority.official_email:
        return ActionStatus.SKIPPED, "There is no department email to remind."
    draft = _create_followup_draft(db, complaint, action, ai=ai, email=email, number=sent + 1)
    return ActionStatus.DONE, f"Reminder {draft.followup_number} drafted. Nothing was sent."


def _create_followup_draft(
    db: Session,
    complaint: Complaint,
    action: ScheduledAction,
    *,
    ai: AIProvider,
    email: EmailProvider,
    number: int,
) -> Communication:
    authority = complaint.authority
    assert authority is not None and authority.official_email
    user = db.get(User, complaint.user_id)
    assert user is not None
    sent = [
        m
        for m in _followups(db, complaint)
        if m.delivery_status in _SENT and m.followup_number is not None
    ]
    department_replied = any(
        m.reply_kind in (ReplyKind.ACKNOWLEDGMENT.value, ReplyKind.IN_PROGRESS.value)
        for m in _replies(db, complaint)
    )
    facts = build_followup_facts(
        complaint,
        user,
        number=number,
        previous_reminder_at=sent[-1].sent_at if sent else None,
        department_replied=department_replied,
    )
    prose, is_mock = ai_service.write_followup_prose(db, ai, complaint, facts)
    subject, body = render_followup(prose, facts)
    draft = Communication(
        complaint_id=complaint.id,
        authority_id=authority.id,
        direction="OUTBOUND",
        communication_type="FOLLOW_UP",
        channel="EMAIL",
        recipient=authority.official_email,
        sender=get_settings().email_from_address,
        subject=subject,
        body=body,
        attachments=[],
        delivery_status="DRAFT",
        is_simulated=email.is_simulated,
        provider=email.name,
        # One draft per check, ever: re-running the same check can't create a second one.
        idempotency_key=f"followup:{action.id}",
        followup_number=number,
    )
    db.add(draft)
    db.flush()
    waited_for = "an update" if department_replied else "a reply"
    complaint_service.record_event(
        db,
        complaint,
        EventType.FOLLOWUP_SUGGESTED,
        f"No {waited_for} by the deadline. Reminder {number} is ready for you to review. "
        "Nothing has been sent.",
        actor=Actor.SYSTEM,
        details={"communication_id": str(draft.id), "is_mock": is_mock},
    )
    return draft


def draft_not_fixed_notice(
    db: Session,
    complaint: Complaint,
    *,
    email: EmailProvider,
    key: str,
    came_back: bool,
    notes: str | None,
) -> Communication | None:
    """After the citizen disputes a claimed repair (or reopens a complaint), draft a message
    telling the department. Only a DRAFT: the citizen edits, approves and sends it, or not.
    The caller commits."""
    authority = complaint.authority
    if authority is None or not authority.official_email:
        return None
    stop_monitoring(db, complaint, "the complaint was reopened")  # nothing older left open
    user = db.get(User, complaint.user_id)
    assert user is not None
    facts = build_followup_facts(
        complaint, user, number=0, previous_reminder_at=None, department_replied=True
    )
    subject, body = render_not_fixed_notice(
        facts, came_back=came_back, checked_on=f"{utc_now():%d %B %Y}", notes=notes
    )
    draft = Communication(
        complaint_id=complaint.id,
        authority_id=authority.id,
        direction="OUTBOUND",
        communication_type="FOLLOW_UP",
        channel="EMAIL",
        recipient=authority.official_email,
        sender=get_settings().email_from_address,
        subject=subject,
        body=body,
        attachments=[],
        delivery_status="DRAFT",
        is_simulated=email.is_simulated,
        provider=email.name,
        idempotency_key=key,
        followup_number=None,  # a notice, not a numbered reminder
    )
    db.add(draft)
    db.flush()
    complaint_service.record_event(
        db,
        complaint,
        EventType.FOLLOWUP_SUGGESTED,
        f"A message telling {authority.name} the problem isn't fixed is ready for you to "
        "review. Nothing has been sent.",
        actor=Actor.SYSTEM,
        details={"communication_id": str(draft.id)},
    )
    return draft


# ── Reading: the complaint page and the dashboard ───────────────────────────


def get_monitoring(db: Session, user: User, complaint_id: uuid.UUID) -> MonitoringRead:
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    pending = _pending_check(db, complaint)
    draft = open_followup(db, complaint)
    replies = _replies(db, complaint)
    relevant = [r for r in replies if r.reply_kind not in (None, ReplyKind.UNRELATED.value)]
    escalation_event = db.scalar(
        select(ComplaintEvent)
        .where(
            ComplaintEvent.complaint_id == complaint.id,
            ComplaintEvent.event_type == EventType.ESCALATION_RECOMMENDED.value,
        )
        .limit(1)
    )
    return MonitoringRead(
        monitored=ComplaintStatus(complaint.status) in MONITORED_STATUSES,
        response_due_at=pending.scheduled_at if pending else None,
        deadline_basis=pending.payload.get("basis") if pending else None,
        deadline_official=bool(pending.payload.get("official")) if pending else False,
        followups_sent=sent_followup_count(db, complaint),
        followups_max=get_settings().followup_max_count,
        authority_reference_number=complaint.authority_reference_number,
        open_followup=CommunicationRead.model_validate(draft) if draft else None,
        open_followup_sha256=message_sha256(draft) if draft else None,
        replies_to_review=[
            CommunicationRead.model_validate(r) for r in replies if r.reply_kind is None
        ],
        latest_reply=CommunicationRead.model_validate(relevant[-1]) if relevant else None,
        escalation=EscalationRead(
            recommended_at=escalation_event.created_at,
            reason=escalation_event.description,
            contacts=[AuthorityRead.model_validate(c) for c in escalation_contacts(db, complaint)],
        )
        if escalation_event
        else None,
    )


def attention_items(db: Session, user: User, limit: int = 10) -> list[AttentionItem]:
    """What the citizen should do next, one (most urgent) item per complaint."""
    watched = {*MONITORED_STATUSES, ComplaintStatus.RESOLVED_PENDING_VERIFICATION}
    complaints = db.scalars(
        select(Complaint)
        .where(Complaint.user_id == user.id, Complaint.status.in_([s.value for s in watched]))
        .order_by(Complaint.updated_at.desc(), Complaint.public_reference.desc())
    ).all()
    if not complaints:
        return []
    ids = [c.id for c in complaints]
    messages: dict[uuid.UUID, list[Communication]] = defaultdict(list)
    for message in db.scalars(
        select(Communication).where(Communication.complaint_id.in_(ids)).order_by(Communication.seq)
    ):
        messages[message.complaint_id].append(message)
    escalated = set(
        db.scalars(
            select(ComplaintEvent.complaint_id).where(
                ComplaintEvent.complaint_id.in_(ids),
                ComplaintEvent.event_type == EventType.ESCALATION_RECOMMENDED.value,
            )
        )
    )

    items: list[AttentionItem] = []
    for complaint in complaints:
        found = _attention_for(complaint, messages[complaint.id], complaint.id in escalated)
        if found:
            kind, message = found
            items.append(
                AttentionItem(
                    complaint_id=complaint.id,
                    complaint_reference=complaint.public_reference,
                    complaint_title=complaint.title,
                    kind=kind,
                    message=message,
                )
            )
    return items[:limit]


def _attention_for(
    complaint: Complaint, messages: list[Communication], escalated: bool
) -> tuple[str, str] | None:
    if complaint.status == ComplaintStatus.RESOLVED_PENDING_VERIFICATION.value:
        return "VERIFY_FIX", "The department says it's fixed. Only you can confirm that."
    followups = [m for m in messages if m.communication_type == "FOLLOW_UP"]
    if any(m.delivery_status == "FAILED" for m in followups):
        return "FOLLOWUP_FAILED", "Sending a reminder failed. Nothing was delivered; try again."
    ready = [m for m in followups if m.delivery_status in ("DRAFT", "APPROVED")]
    if ready:
        what = "A reminder" if ready[-1].followup_number else "A message for the department"
        return "FOLLOWUP_READY", f"{what} is ready for you to review. Nothing has been sent."
    replies = [m for m in messages if m.direction == "INBOUND"]
    if any(m.reply_kind is None for m in replies):
        return "REPLY_TO_REVIEW", "A reply arrived. Please tell us what it means."
    relevant = [m for m in replies if m.reply_kind != ReplyKind.UNRELATED.value]
    if relevant and relevant[-1].reply_kind == ReplyKind.REQUEST_FOR_INFO.value:
        later_outbound = any(
            m.direction == "OUTBOUND" and m.seq > relevant[-1].seq and m.delivery_status in _SENT
            for m in messages
        )
        if not later_outbound:
            return "INFO_REQUESTED", "The department asked you for more information."
    if escalated:
        return "ESCALATION", "Escalation is recommended. See the contacts on the complaint page."
    return None


# ── Development / demo simulation (ENABLE_SIMULATION only) ──────────────────


def simulate_reply(
    db: Session,
    ai: AIProvider,
    user: User,
    complaint_id: uuid.UUID,
    *,
    scenario: str | None,
    body: str | None,
) -> Communication:
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    if complaint.submitted_at is None or complaint.status == ComplaintStatus.CANCELLED.value:
        raise ConflictError("Only a submitted complaint can receive a reply.")
    if scenario is not None:
        sample = reply_scenarios(complaint)[scenario]
        subject, text = sample.subject, sample.body
    else:
        subject, text = f"Re: {complaint.public_reference}", body or ""
    reply = receive_reply(db, ai, complaint, subject=subject, body=text, is_simulated=True)
    db.commit()
    return reply


def advance_to_next_check(
    db: Session, *, ai: AIProvider, email: EmailProvider, user: User, complaint_id: uuid.UUID
) -> list[ScheduledAction]:
    """Demo time travel for ONE complaint: run its next check as if its date had arrived."""
    complaint = complaint_service.get_owned_complaint(db, user, complaint_id)
    pending = _pending_check(db, complaint)
    if pending is None:
        raise ConflictError("Nothing is scheduled for this complaint right now.")
    now = max(utc_now(), pending.scheduled_at)
    return run_due_actions(db, ai=ai, email=email, now=now, complaint_id=complaint.id, limit=1)

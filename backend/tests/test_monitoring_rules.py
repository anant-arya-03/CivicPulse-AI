"""The monitoring rules on their own (no database): deadlines, anti-spam, reply effects,
reference numbers."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.complaints.constants import ComplaintStatus as S
from app.modules.monitoring import rules
from app.modules.monitoring.constants import CheckTrigger, ReplyKind

SENT = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)


def check(trigger: CheckTrigger, *, at: datetime = SENT, timeline: int | None = None):
    return rules.next_check(
        trigger,
        at=at,
        submitted_at=SENT,
        service_timeline_days=timeline,
        first_after_days=7,
        interval_days=5,
    )


# ── Deadlines ───────────────────────────────────────────────────────────────


def test_deadline_uses_the_departments_listed_response_time() -> None:
    deadline = check(CheckTrigger.COMPLAINT_SENT, timeline=15)
    assert deadline.due_at == SENT + timedelta(days=15)
    assert deadline.official is True
    assert "15 days" in deadline.basis


def test_deadline_falls_back_to_the_default_and_says_so() -> None:
    deadline = check(CheckTrigger.COMPLAINT_SENT)
    assert deadline.due_at == SENT + timedelta(days=7)
    assert deadline.official is False
    assert "no response time is listed" in deadline.basis


def test_after_a_reminder_the_interval_applies() -> None:
    later = SENT + timedelta(days=8)
    deadline = check(CheckTrigger.FOLLOWUP_SENT, at=later, timeline=15)
    assert deadline.due_at == later + timedelta(days=5)
    assert deadline.official is False


def test_an_acknowledgment_gives_the_department_its_full_listed_time() -> None:
    # Acknowledged on day 1: the listed 15 days still apply, not "1 day + 5".
    deadline = check(CheckTrigger.PROGRESS_REPLY, at=SENT + timedelta(days=1), timeline=15)
    assert deadline.due_at == SENT + timedelta(days=15)
    assert deadline.official is True


def test_a_late_progress_reply_gets_one_more_interval() -> None:
    reply_at = SENT + timedelta(days=20)
    deadline = check(CheckTrigger.PROGRESS_REPLY, at=reply_at, timeline=15)
    assert deadline.due_at == reply_at + timedelta(days=5)
    assert "last update" in deadline.basis


# ── Anti-spam ───────────────────────────────────────────────────────────────


def test_reminders_are_allowed_only_while_waiting_and_under_the_limit() -> None:
    def blocker(**overrides: object) -> str | None:
        args: dict = {
            "status": S.SUBMITTED,
            "sent_count": 0,
            "max_count": 2,
            "has_open_followup": False,
        }
        args.update(overrides)
        return rules.followup_blocker(**args)

    assert blocker() is None
    assert blocker(status=S.ACKNOWLEDGED) is None
    assert "limit" in (blocker(sent_count=2) or "")
    assert "already waiting" in (blocker(has_open_followup=True) or "")
    for finished in (S.RESOLVED_PENDING_VERIFICATION, S.CLOSED, S.CANCELLED, S.DRAFT):
        assert blocker(status=finished) is not None


# ── Reply effects ───────────────────────────────────────────────────────────


def test_acknowledgment_moves_on_and_keeps_watching() -> None:
    effect = rules.reply_effect(ReplyKind.ACKNOWLEDGMENT, S.SUBMITTED)
    assert effect.new_status == S.ACKNOWLEDGED
    assert effect.stop_reminders and effect.keep_checking
    assert not effect.recommend_escalation


def test_acknowledgment_never_moves_a_complaint_backwards() -> None:
    effect = rules.reply_effect(ReplyKind.ACKNOWLEDGMENT, S.IN_PROGRESS)
    assert effect.new_status is None
    assert effect.keep_checking


def test_resolved_claim_needs_the_citizen_and_stops_reminders() -> None:
    effect = rules.reply_effect(ReplyKind.RESOLVED_CLAIM, S.ACKNOWLEDGED)
    assert effect.new_status == S.RESOLVED_PENDING_VERIFICATION
    assert effect.stop_reminders and not effect.keep_checking
    assert "Only you can confirm" in effect.status_note


@pytest.mark.parametrize("kind", list(ReplyKind))
@pytest.mark.parametrize("status", list(S))
def test_no_reply_can_close_verify_or_skip_the_citizen(kind: ReplyKind, status: S) -> None:
    effect = rules.reply_effect(kind, status)
    assert effect.new_status not in (S.VERIFIED_RESOLVED, S.CLOSED, S.CANCELLED, S.REOPENED)


def test_request_for_info_and_rejection_stop_reminders() -> None:
    info = rules.reply_effect(ReplyKind.REQUEST_FOR_INFO, S.SUBMITTED)
    assert info.new_status is None and info.stop_reminders and not info.keep_checking
    rejected = rules.reply_effect(ReplyKind.REJECTION, S.SUBMITTED)
    assert rejected.stop_reminders and rejected.recommend_escalation


def test_unrelated_reply_changes_nothing() -> None:
    effect = rules.reply_effect(ReplyKind.UNRELATED, S.SUBMITTED)
    assert effect.new_status is None
    assert not (effect.stop_reminders or effect.keep_checking or effect.recommend_escalation)


def test_only_confident_ai_readings_are_applied_automatically() -> None:
    assert rules.should_auto_apply("HIGH") and rules.should_auto_apply("MEDIUM")
    assert not rules.should_auto_apply("LOW")


# ── Reference numbers ───────────────────────────────────────────────────────

OURS = "CP-2026-000123"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Your reference number is DC-RD-000123.", "DC-RD-000123"),
        ("Ref. No.: 2026/rd/0412 has been assigned", "2026/RD/0412"),
        ("ticket #A1234 opened", "A1234"),
        ("Docket: X-77", "X-77"),
        ("We registered your complaint CP-2026-000123 as grievance GR-55", "GR-55"),
    ],
)
def test_reference_numbers_are_found(text: str, expected: str) -> None:
    assert rules.find_reference_number(text, own_reference=OURS) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Thank you for your complaint CP-2026-000123.",  # only our own reference
        "Your reference will follow shortly.",  # no digits
        "Reference: <script>alert(1)</script>",
        "No numbers here at all.",
    ],
)
def test_no_reference_number_is_invented(text: str) -> None:
    assert rules.find_reference_number(text, own_reference=OURS) is None


def test_ai_reference_must_appear_in_the_reply() -> None:
    text = "Registered as DC-RD-000123."
    assert rules.accept_reference("dc-rd-000123", text, own_reference=OURS) == "DC-RD-000123"
    assert rules.accept_reference("DC-RD-999999", text, own_reference=OURS) is None  # invented
    assert rules.accept_reference(OURS, f"{text} {OURS}", own_reference=OURS) is None
    assert rules.accept_reference("https://evil.example", text, own_reference=OURS) is None
    assert rules.accept_reference(None, text, own_reference=OURS) is None

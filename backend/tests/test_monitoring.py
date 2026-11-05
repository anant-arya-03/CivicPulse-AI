"""Response monitoring and follow-ups, end to end through the API and the worker.

Cases: unanswered (reminders, then escalation), acknowledged, in progress, resolved, request for
information, rejection, unrelated replies, AI failure (manual path), prompt injection, failed
sends and failing scheduled actions, duplicates, withdrawal, and authorization.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.core.config import get_settings
from app.integrations.ai_providers.mock_provider import MockAIProvider
from app.integrations.email_providers.mock_provider import MockEmailProvider
from app.modules.authorities.models import Authority
from app.modules.communications.models import Communication
from app.modules.complaints.models import Complaint
from app.modules.monitoring import service as monitoring
from app.modules.monitoring.constants import CheckTrigger
from app.modules.monitoring.models import ScheduledAction
from tests.conftest import csrf_headers, register
from tests.test_submission import approve, events, ready_complaint, send, status_of

API = "/api/v1"


@pytest.fixture(autouse=True)
def simulation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulation on, and fixed follow-up settings, whatever the local .env says."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_simulation", True)
    monkeypatch.setattr(settings, "followup_first_after_days", 7)
    monkeypatch.setattr(settings, "followup_interval_days", 7)
    monkeypatch.setattr(settings, "followup_max_count", 2)
    monkeypatch.setattr(settings, "scheduler_max_attempts", 3)


# ── Helpers ─────────────────────────────────────────────────────────────────


def submitted_complaint(client: TestClient, db: Session) -> dict:
    register(client)
    complaint = ready_complaint(client, db)
    message = approve(client, complaint["id"]).json()
    assert send(client, message["id"]).status_code == 200
    return complaint


def monitoring_of(client: TestClient, complaint_id: str) -> dict:
    response = client.get(f"{API}/complaints/{complaint_id}/monitoring")
    assert response.status_code == 200, response.text
    return response.json()


def run_worker(db: Session, ai: MockAIProvider, email: MockEmailProvider, days: float):
    """Run the worker as if `days` days had passed."""
    return monitoring.run_due_actions(db, ai=ai, email=email, now=utc_now() + timedelta(days=days))


def simulate(client: TestClient, complaint_id: str, scenario: str | None = None, body: str = ""):
    payload = {"scenario": scenario} if scenario else {"body": body}
    return client.post(
        f"{API}/complaints/{complaint_id}/simulation/reply",
        json=payload,
        headers=csrf_headers(client),
    )


def approve_followup(client: TestClient, complaint_id: str):
    state = monitoring_of(client, complaint_id)
    return client.post(
        f"{API}/communications/{state['open_followup']['id']}/approve",
        json={"confirm": True, "content_sha256": state["open_followup_sha256"]},
        headers=csrf_headers(client),
    )


def actions(db: Session, complaint_id: str) -> list[ScheduledAction]:
    return list(
        db.scalars(
            select(ScheduledAction)
            .where(ScheduledAction.complaint_id == uuid.UUID(complaint_id))
            .order_by(ScheduledAction.created_at)
        ).all()
    )


def pending(db: Session, complaint_id: str) -> list[ScheduledAction]:
    return [a for a in actions(db, complaint_id) if a.execution_status == "PENDING"]


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ── Deadlines ───────────────────────────────────────────────────────────────


def test_submission_schedules_a_check_at_the_listed_response_time(
    client: TestClient, db: Session, demo_directory: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    roads = db.scalar(select(Authority).where(Authority.name.like("%Roads%")))
    assert roads is not None
    roads.service_timeline_days = 15
    complaint = submitted_complaint(client, db)

    state = monitoring_of(client, complaint["id"])
    submitted_at = parse(client.get(f"{API}/complaints/{complaint['id']}").json()["submitted_at"])
    assert state["monitored"] is True
    assert parse(state["response_due_at"]) - submitted_at == timedelta(days=15)
    assert state["deadline_official"] is True
    assert "15 days" in state["deadline_basis"]
    assert state["followups_sent"] == 0 and state["followups_max"] == 2


def test_without_a_listed_time_the_default_is_used_and_labelled(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    roads = db.scalar(select(Authority).where(Authority.name.like("%Roads%")))
    assert roads is not None
    roads.service_timeline_days = None
    complaint = submitted_complaint(client, db)
    state = monitoring_of(client, complaint["id"])
    assert state["deadline_official"] is False
    assert "default of 7 days" in state["deadline_basis"]


# ── Unanswered: reminders (never sent automatically), then escalation ───────


def test_nothing_happens_before_the_deadline(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    assert run_worker(db, ai, email, days=6) == []
    assert monitoring_of(client, complaint["id"])["open_followup"] is None


def test_unanswered_complaint_gets_a_draft_reminder_that_is_not_sent(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    emails_before = len(email.sent)

    ran = run_worker(db, ai, email, days=8)
    assert [a.execution_status for a in ran] == ["DONE"]
    state = monitoring_of(client, complaint["id"])
    draft = state["open_followup"]
    assert draft["delivery_status"] == "DRAFT"
    assert draft["communication_type"] == "FOLLOW_UP"
    assert draft["followup_number"] == 1
    assert draft["recipient"] == "roads@demo-city.example"
    assert draft["is_simulated"] is True
    assert draft["subject"].startswith("Reminder 1:")
    assert complaint["public_reference"] in draft["body"]
    assert "Complaint submitted on:" in draft["body"]  # facts from the template
    assert len(email.sent) == emails_before  # NOTHING was sent
    assert events(client, complaint["id"])[-1] == "FOLLOWUP_SUGGESTED"

    # Running the worker again (or later) never creates a second draft.
    assert run_worker(db, ai, email, days=30) == []
    assert run_worker(db, ai, email, days=8) == []
    drafts = [
        m
        for m in client.get(f"{API}/complaints/{complaint['id']}/communications").json()
        if m["communication_type"] == "FOLLOW_UP"
    ]
    assert len(drafts) == 1


def test_full_unanswered_journey_ends_in_an_escalation_recommendation(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    for number in (1, 2):
        run_worker(db, ai, email, days=8 * number)
        assert approve_followup(client, complaint["id"]).status_code == 200
        draft_id = monitoring_of(client, complaint["id"])["open_followup"]["id"]
        sent = send(client, draft_id).json()
        assert sent["delivery_status"] == "SIMULATED_SENT"
        assert sent["followup_number"] == number
        assert monitoring_of(client, complaint["id"])["followups_sent"] == number

    assert len(email.sent) == 3  # the complaint + 2 approved reminders, nothing more
    ran = run_worker(db, ai, email, days=40)
    assert [a.outcome for a in ran] == ["No reply after the maximum number of reminders."]
    state = monitoring_of(client, complaint["id"])
    assert state["open_followup"] is None  # no third reminder
    escalation = state["escalation"]
    assert "hasn't replied after 2 reminder(s)" in escalation["reason"]
    assert [c["name"] for c in escalation["contacts"]] == [
        "Demo City Municipal Commissioner's Office"
    ]
    assert escalation["contacts"][0]["is_demo"] is True
    assert "does not contact them for you" in escalation["reason"]
    assert len(email.sent) == 3  # escalation contacts nobody

    # The escalation is recorded once, however often the worker runs.
    run_worker(db, ai, email, days=60)
    assert events(client, complaint["id"]).count("ESCALATION_RECOMMENDED") == 1


def test_escalation_without_a_higher_office_never_guesses_one(
    client: TestClient, db: Session, demo_directory: None, ai, email, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "followup_max_count", 0)
    roads = db.scalar(select(Authority).where(Authority.name.like("%Roads%")))
    assert roads is not None
    roads.parent_authority_id = None
    complaint = submitted_complaint(client, db)
    run_worker(db, ai, email, days=8)
    escalation = monitoring_of(client, complaint["id"])["escalation"]
    assert escalation["contacts"] == []
    assert "never guesses contact details" in escalation["reason"]


def test_reminder_wording_falls_back_to_the_template_when_ai_fails(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    ai.scenario = "failure"
    run_worker(db, ai, email, days=8)
    draft = monitoring_of(client, complaint["id"])["open_followup"]
    assert "I have not yet received a reply." in draft["body"]
    assert "AI_ANALYSIS_FAILED" in events(client, complaint["id"])


# ── Approval, editing, dismissing ───────────────────────────────────────────


def test_reminder_needs_explicit_approval_of_the_exact_content(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    run_worker(db, ai, email, days=8)
    state = monitoring_of(client, complaint["id"])
    draft_id = state["open_followup"]["id"]
    headers = csrf_headers(client)

    assert send(client, draft_id).status_code == 409  # not approved yet
    no_confirm = client.post(
        f"{API}/communications/{draft_id}/approve",
        json={"confirm": False, "content_sha256": state["open_followup_sha256"]},
        headers=headers,
    )
    assert no_confirm.status_code == 422
    stale = client.post(
        f"{API}/communications/{draft_id}/approve",
        json={"confirm": True, "content_sha256": "0" * 64},
        headers=headers,
    )
    assert stale.status_code == 409

    approved = approve_followup(client, complaint["id"])
    assert approved.json()["delivery_status"] == "APPROVED"
    assert approve_followup(client, complaint["id"]).status_code == 200  # idempotent

    # Editing after approval withdraws it: the old approval can't send the new words.
    edited = client.patch(
        f"{API}/communications/{draft_id}",
        json={"body": "Dear Sir or Madam, this is my own reminder text. Please reply."},
        headers=headers,
    )
    assert edited.json()["delivery_status"] == "DRAFT"
    assert send(client, draft_id).status_code == 409
    assert approve_followup(client, complaint["id"]).status_code == 200
    assert send(client, draft_id).json()["body"].startswith("Dear Sir or Madam, this is my own")


def test_dismissing_a_reminder_sends_nothing_and_checks_again_later(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    run_worker(db, ai, email, days=8)
    draft_id = monitoring_of(client, complaint["id"])["open_followup"]["id"]
    response = client.post(f"{API}/communications/{draft_id}/dismiss", headers=csrf_headers(client))
    assert response.json()["delivery_status"] == "CANCELLED"
    assert send(client, draft_id).status_code == 409
    assert len(email.sent) == 1
    assert len(pending(db, complaint["id"])) == 1  # a new check, one interval later
    assert "FOLLOWUP_DISMISSED" in events(client, complaint["id"])


# ── Replies ─────────────────────────────────────────────────────────────────


def test_acknowledgment_records_the_reference_and_cancels_the_reminder(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    run_worker(db, ai, email, days=8)  # a reminder is waiting
    draft_id = monitoring_of(client, complaint["id"])["open_followup"]["id"]

    reply = simulate(client, complaint["id"], "acknowledged")
    assert reply.status_code == 201, reply.text
    body = reply.json()
    assert body["direction"] == "INBOUND" and body["is_simulated"] is True
    assert body["reply_kind"] == "ACKNOWLEDGMENT" and body["reply_kind_source"] == "AI"
    expected_ref = "DC-RD-" + complaint["public_reference"].rsplit("-", 1)[-1]
    assert body["reference_number"] == expected_ref

    assert status_of(client, complaint["id"]) == "ACKNOWLEDGED"
    state = monitoring_of(client, complaint["id"])
    assert state["authority_reference_number"] == expected_ref
    assert state["open_followup"] is None  # the unsent reminder was cancelled
    assert db.get(Communication, uuid.UUID(draft_id)).delivery_status == "CANCELLED"  # type: ignore[union-attr]
    assert state["monitored"] is True and state["response_due_at"] is not None  # still watched
    timeline = events(client, complaint["id"])
    for event in (
        "REPLY_RECEIVED",
        "REPLY_CLASSIFIED",
        "REFERENCE_NUMBER_RECORDED",
        "FOLLOWUPS_STOPPED",
        "STATUS_CHANGED",
    ):
        assert event in timeline
    assert len(email.sent) == 1


def test_in_progress_reply(client: TestClient, db: Session, demo_directory: None) -> None:
    complaint = submitted_complaint(client, db)
    simulate(client, complaint["id"], "acknowledged")
    simulate(client, complaint["id"], "in_progress")
    assert status_of(client, complaint["id"]) == "IN_PROGRESS"
    # A late "acknowledged" never moves it backwards.
    simulate(client, complaint["id"], "acknowledged")
    assert status_of(client, complaint["id"]) == "IN_PROGRESS"


def test_resolved_claim_stops_everything_and_waits_for_the_citizen(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    run_worker(db, ai, email, days=8)
    simulate(client, complaint["id"], "resolved")

    assert status_of(client, complaint["id"]) == "RESOLVED_PENDING_VERIFICATION"
    state = monitoring_of(client, complaint["id"])
    assert state["monitored"] is False
    assert state["open_followup"] is None and state["response_due_at"] is None
    assert pending(db, complaint["id"]) == []
    assert run_worker(db, ai, email, days=60) == []  # nothing left to do
    dashboard = client.get(f"{API}/dashboard/summary").json()
    assert dashboard["needs_attention"][0]["kind"] == "VERIFY_FIX"


def test_request_for_info_stops_reminders_and_asks_the_citizen(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = submitted_complaint(client, db)
    simulate(client, complaint["id"], "need_info")
    assert status_of(client, complaint["id"]) == "SUBMITTED"
    assert pending(db, complaint["id"]) == []
    dashboard = client.get(f"{API}/dashboard/summary").json()
    assert dashboard["needs_attention"][0]["kind"] == "INFO_REQUESTED"


def test_rejection_recommends_escalation(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = submitted_complaint(client, db)
    simulate(client, complaint["id"], "rejected")
    state = monitoring_of(client, complaint["id"])
    assert "declined" in state["escalation"]["reason"]
    assert pending(db, complaint["id"]) == []


def test_unrelated_auto_reply_changes_nothing(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = submitted_complaint(client, db)
    check_before = pending(db, complaint["id"])[0].id
    reply = simulate(client, complaint["id"], "auto_reply").json()
    assert reply["reply_kind"] == "UNRELATED"
    assert status_of(client, complaint["id"]) == "SUBMITTED"
    assert [a.id for a in pending(db, complaint["id"])] == [check_before]  # same deadline


def test_ai_failure_means_the_citizen_decides(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    ai.scenario = "failure"
    reply = simulate(client, complaint["id"], "acknowledged").json()
    assert reply["reply_kind"] is None
    assert reply["reference_number"] is not None  # found without AI, not applied yet
    assert status_of(client, complaint["id"]) == "SUBMITTED"  # nothing decided for the citizen
    state = monitoring_of(client, complaint["id"])
    assert [r["id"] for r in state["replies_to_review"]] == [reply["id"]]
    assert state["authority_reference_number"] is None
    dashboard = client.get(f"{API}/dashboard/summary").json()
    assert dashboard["needs_attention"][0]["kind"] == "REPLY_TO_REVIEW"

    # While a reply waits for review, no reminder is drafted over it.
    ran = run_worker(db, ai, email, days=8)
    assert [a.execution_status for a in ran] == ["SKIPPED"]
    assert "reply means" in (ran[0].outcome or "")

    headers = csrf_headers(client)
    url = f"{API}/communications/{reply['id']}/reply-kind"
    response = client.put(url, json={"kind": "ACKNOWLEDGMENT"}, headers=headers)
    assert response.json()["reply_kind_source"] == "CITIZEN"
    assert status_of(client, complaint["id"]) == "ACKNOWLEDGED"
    assert monitoring_of(client, complaint["id"])["authority_reference_number"] is not None
    assert client.put(url, json={"kind": "REJECTION"}, headers=headers).status_code == 409
    assert client.put(url, json={"kind": "MAYBE"}, headers=headers).status_code == 422


def test_invalid_ai_output_also_falls_back_to_the_citizen(
    client: TestClient, db: Session, demo_directory: None, ai
) -> None:
    complaint = submitted_complaint(client, db)
    ai.scenario = "invalid"
    reply = simulate(client, complaint["id"], "resolved").json()
    assert reply["reply_kind"] is None
    assert status_of(client, complaint["id"]) == "SUBMITTED"


def test_prompt_injection_in_a_reply_cannot_do_more_than_a_normal_reply(
    client: TestClient, db: Session, demo_directory: None, email
) -> None:
    complaint = submitted_complaint(client, db)
    reply = simulate(client, complaint["id"], "injection").json()

    # The demo AI falls for the word "resolved". Even so, that is the worst possible effect:
    # "the department says it's fixed", which still needs the citizen to verify. It isn't
    # verified, closed or cancelled, and nothing is sent.
    assert status_of(client, complaint["id"]) == "RESOLVED_PENDING_VERIFICATION"
    assert reply["reference_number"] is None
    summary = reply["reply_summary"] or ""
    assert "evil.example" not in summary and "@" not in summary
    assert "SYSTEM INSTRUCTION" in reply["body"]  # stored as text, shown as text
    outbound = [
        m
        for m in client.get(f"{API}/complaints/{complaint['id']}/communications").json()
        if m["direction"] == "OUTBOUND"
    ]
    assert len(outbound) == 1 and len(email.sent) == 1  # nothing new was sent to anyone


def test_custom_reply_text_is_cleaned_and_length_checked(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = submitted_complaint(client, db)
    reply = simulate(client, complaint["id"], body="Hello\x00 we \x07received it\r\nThanks").json()
    assert reply["body"] == "Hello we received it\nThanks"
    assert simulate(client, complaint["id"], body="x" * 5001).status_code == 422
    both = client.post(
        f"{API}/complaints/{complaint['id']}/simulation/reply",
        json={"scenario": "resolved", "body": "Hello there"},
        headers=csrf_headers(client),
    )
    assert both.status_code == 422


# ── Failures ────────────────────────────────────────────────────────────────


def test_failed_reminder_send_delivers_nothing_and_can_be_retried(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    run_worker(db, ai, email, days=8)
    approve_followup(client, complaint["id"])
    draft_id = monitoring_of(client, complaint["id"])["open_followup"]["id"]

    email.scenario = "failure"
    failed = send(client, draft_id)
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "SUBMISSION_FAILED"
    assert len(email.sent) == 1
    assert monitoring_of(client, complaint["id"])["open_followup"]["delivery_status"] == "FAILED"
    assert events(client, complaint["id"])[-1] == "FOLLOWUP_FAILED"
    dashboard = client.get(f"{API}/dashboard/summary").json()
    assert dashboard["needs_attention"][0]["kind"] == "FOLLOWUP_FAILED"
    assert run_worker(db, ai, email, days=30) == []  # a failed reminder is not re-drafted

    email.scenario = "success"
    retried = send(client, draft_id).json()
    assert retried["delivery_status"] == "SIMULATED_SENT" and retried["attempt_count"] == 2
    assert len(email.sent) == 2


def test_a_failing_scheduled_action_is_retried_then_marked_failed(
    client: TestClient,
    db: Session,
    demo_directory: None,
    ai,
    email,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    complaint = submitted_complaint(client, db)

    def broken(*args: object, **kwargs: object):
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(monitoring, "_run_followup_check", broken)
    now = utc_now() + timedelta(days=8)
    first = monitoring.run_due_actions(db, ai=ai, email=email, now=now)
    action = first[0]
    assert action.execution_status == "PENDING" and action.attempt_count == 1
    assert action.scheduled_at > now  # backs off before retrying
    assert "database hiccup" in (action.last_error or "")

    for _ in range(5):
        now += timedelta(hours=2)
        monitoring.run_due_actions(db, ai=ai, email=email, now=now)
    db.refresh(action)
    assert action.execution_status == "FAILED" and action.attempt_count == 3
    assert monitoring_of(client, complaint["id"])["open_followup"] is None


def test_a_stuck_running_action_is_picked_up_again(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    action = pending(db, complaint["id"])[0]
    action.execution_status = "RUNNING"  # a worker crashed mid-run...
    db.commit()
    assert run_worker(db, ai, email, days=8) == []  # ...recently: leave it alone
    action.updated_at = utc_now() - timedelta(hours=1)  # ...long ago: run it again
    db.commit()
    ran = run_worker(db, ai, email, days=8)
    assert [a.id for a in ran] == [action.id]
    assert ran[0].execution_status == "DONE"


# ── Duplicates ──────────────────────────────────────────────────────────────


def test_sending_a_reminder_twice_sends_it_once(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    run_worker(db, ai, email, days=8)
    approve_followup(client, complaint["id"])
    draft_id = monitoring_of(client, complaint["id"])["open_followup"]["id"]
    first = send(client, draft_id).json()
    second = send(client, draft_id).json()
    assert first["id"] == second["id"] and second["delivery_status"] == "SIMULATED_SENT"
    assert len(email.sent) == 2  # complaint + one reminder
    assert events(client, complaint["id"]).count("FOLLOWUP_SENT") == 1
    assert len(pending(db, complaint["id"])) == 1  # one next check, not two


def test_the_same_check_can_never_be_scheduled_twice(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = submitted_complaint(client, db)
    message = db.scalar(
        select(Communication).where(Communication.complaint_id == uuid.UUID(complaint["id"]))
    )
    row = db.get(Complaint, uuid.UUID(complaint["id"]))
    assert message is not None and row is not None
    again = monitoring.schedule_check(
        db, row, CheckTrigger.COMPLAINT_SENT, at=utc_now(), after=message
    )
    assert again is not None and len(actions(db, complaint["id"])) == 1


def test_a_reply_after_the_deadline_prevents_a_reminder(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    """Defence in depth: even an old pending check re-checks for replies when it runs."""
    complaint = submitted_complaint(client, db)
    old_check = pending(db, complaint["id"])[0]
    simulate(client, complaint["id"], "acknowledged")  # cancels it...
    old_check.execution_status = "PENDING"  # ...but pretend the cancel was lost
    db.commit()
    ran = run_worker(db, ai, email, days=8)
    assert ran[0].execution_status == "SKIPPED"
    assert ran[0].outcome == "Not needed: the department replied."


# ── Withdrawal ──────────────────────────────────────────────────────────────


def test_withdrawing_a_submitted_complaint_cancels_checks_and_reminders(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    run_worker(db, ai, email, days=8)
    draft_id = monitoring_of(client, complaint["id"])["open_followup"]["id"]
    response = client.post(
        f"{API}/complaints/{complaint['id']}/cancel", headers=csrf_headers(client)
    )
    assert response.json()["status"] == "CANCELLED"
    assert db.get(Communication, uuid.UUID(draft_id)).delivery_status == "CANCELLED"  # type: ignore[union-attr]
    assert monitoring_of(client, complaint["id"])["open_followup"] is None
    assert send(client, draft_id).status_code == 409
    assert run_worker(db, ai, email, days=60) == []
    timeline = client.get(f"{API}/complaints/{complaint['id']}/timeline").json()
    assert any("not notified automatically" in e["description"] for e in timeline)
    assert len(email.sent) == 1


def test_closing_an_acknowledged_complaint_stops_monitoring(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    simulate(client, complaint["id"], "acknowledged")
    assert len(pending(db, complaint["id"])) == 1
    client.post(f"{API}/complaints/{complaint['id']}/close", headers=csrf_headers(client))
    assert pending(db, complaint["id"]) == []
    assert run_worker(db, ai, email, days=60) == []


# ── Simulation switches and authorization ───────────────────────────────────


def test_simulation_endpoints_do_not_exist_when_disabled(
    client: TestClient, db: Session, demo_directory: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    complaint = submitted_complaint(client, db)
    monkeypatch.setattr(get_settings(), "enable_simulation", False)
    assert simulate(client, complaint["id"], "resolved").status_code == 404
    advance = client.post(
        f"{API}/complaints/{complaint['id']}/simulation/advance", headers=csrf_headers(client)
    )
    assert advance.status_code == 404
    assert client.get(f"{API}/simulation").json() == {"enabled": False, "reply_scenarios": []}


def test_simulation_rules(client: TestClient, db: Session, demo_directory: None) -> None:
    register(client)
    draft = ready_complaint(client, db)
    assert simulate(client, draft["id"], "resolved").status_code == 409  # not submitted
    advance = client.post(
        f"{API}/complaints/{draft['id']}/simulation/advance", headers=csrf_headers(client)
    )
    assert advance.status_code == 409
    info = client.get(f"{API}/simulation").json()
    assert info["enabled"] is True
    assert {s["id"] for s in info["reply_scenarios"]} >= {"acknowledged", "injection"}


def test_advance_runs_only_this_complaints_next_check(
    client: TestClient, db: Session, demo_directory: None, email
) -> None:
    complaint = submitted_complaint(client, db)
    response = client.post(
        f"{API}/complaints/{complaint['id']}/simulation/advance", headers=csrf_headers(client)
    )
    assert response.status_code == 200, response.text
    assert [a["execution_status"] for a in response.json()["ran"]] == ["DONE"]
    assert monitoring_of(client, complaint["id"])["open_followup"]["delivery_status"] == "DRAFT"
    assert len(email.sent) == 1


def test_other_users_cannot_see_or_touch_monitoring(
    client: TestClient, other_client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = submitted_complaint(client, db)
    run_worker(db, ai, email, days=8)
    draft_id = monitoring_of(client, complaint["id"])["open_followup"]["id"]
    reply = simulate(client, complaint["id"], body="Some unclear message text").json()
    headers = csrf_headers(other_client)
    cid = complaint["id"]

    assert other_client.get(f"{API}/complaints/{cid}/monitoring").status_code == 404
    for path in ("simulation/reply", "simulation/advance"):
        response = other_client.post(
            f"{API}/complaints/{cid}/{path}", json={"scenario": "resolved"}, headers=headers
        )
        assert response.status_code == 404
    for verb, path, payload in (
        ("patch", f"/communications/{draft_id}", {"subject": "Taken over subject"}),
        (
            "post",
            f"/communications/{draft_id}/approve",
            {"confirm": True, "content_sha256": "0" * 64},
        ),
        ("post", f"/communications/{draft_id}/dismiss", None),
        ("post", f"/communications/{draft_id}/send", None),
        ("put", f"/communications/{reply['id']}/reply-kind", {"kind": "RESOLVED_CLAIM"}),
    ):
        response = getattr(other_client, verb)(f"{API}{path}", json=payload, headers=headers)
        assert response.status_code == 404, (path, response.text)
    assert monitoring_of(client, cid)["open_followup"]["delivery_status"] == "DRAFT"
    assert status_of(client, cid) == "SUBMITTED"

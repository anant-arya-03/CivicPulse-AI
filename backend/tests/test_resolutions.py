"""Resolution verification end to end: follow-up photos, the AI comparison (advice only),
the citizen's confirm / dispute, reopening, the audit trail, and ownership."""

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.ai.models import AIAnalysis
from app.modules.monitoring.models import ScheduledAction
from app.modules.resolutions.models import ResolutionReview
from app.modules.resolutions.rules import ALWAYS
from tests.conftest import csrf_headers, make_image, upload_photo
from tests.test_monitoring import monitoring_of, run_worker, simulate, submitted_complaint
from tests.test_submission import events, ready_complaint, send, status_of

API = "/api/v1"


@pytest.fixture(autouse=True)
def simulation(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_simulation", True)
    monkeypatch.setattr(settings, "followup_first_after_days", 7)
    monkeypatch.setattr(settings, "followup_interval_days", 7)
    monkeypatch.setattr(settings, "followup_max_count", 2)


# ── Helpers ─────────────────────────────────────────────────────────────────


def new_photo(seed: int = 1, **kwargs: object) -> bytes:
    """A photo different from the original (which is make_image() with default settings)."""
    return make_image(size=(320 + seed, 240), **kwargs)  # type: ignore[arg-type]


def upload_after(client: TestClient, complaint_id: str, data: bytes | None = None):
    return client.post(
        f"{API}/complaints/{complaint_id}/followup-evidence",
        files={"file": ("after.jpg", data if data is not None else new_photo(), "image/jpeg")},
        headers=csrf_headers(client),
    )


def review_for(client: TestClient, complaint_id: str, evidence_id: str):
    return client.post(
        f"{API}/complaints/{complaint_id}/resolution-reviews",
        json={"evidence_id": evidence_id},
        headers=csrf_headers(client),
    )


def checked(client: TestClient, complaint_id: str, data: bytes | None = None) -> dict:
    """Upload an after-photo and get the AI comparison."""
    photo = upload_after(client, complaint_id, data)
    assert photo.status_code == 201, photo.text
    response = review_for(client, complaint_id, photo.json()["id"])
    assert response.status_code == 201, response.text
    return response.json()


def decide(client: TestClient, review_id: str, decision: str, **extra: object):
    payload: dict = {"decision": decision, "checked_myself": True}
    payload.update(extra)
    return client.post(
        f"{API}/resolution-reviews/{review_id}/decision", json=payload, headers=csrf_headers(client)
    )


def claimed_fixed(client: TestClient, db: Session) -> dict:
    """A submitted complaint whose department says it's fixed (simulated reply)."""
    complaint = submitted_complaint(client, db)
    simulate(client, complaint["id"], "resolved")
    assert status_of(client, complaint["id"]) == "RESOLVED_PENDING_VERIFICATION"
    return complaint


# ── Follow-up photos ────────────────────────────────────────────────────────


def test_after_photos_need_a_sent_complaint(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    from tests.conftest import register

    register(client)
    draft = ready_complaint(client, db)
    assert upload_after(client, draft["id"]).status_code == 409


def test_after_photo_is_validated_and_cleaned_like_the_original(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    response = upload_after(client, complaint["id"], new_photo(with_gps_exif=True))
    assert response.status_code == 201, response.text
    photo = response.json()
    assert photo["evidence_type"] == "FOLLOWUP"
    stored = client.get(photo["url"])
    assert stored.status_code == 200
    assert stored.headers["cache-control"].startswith("private")
    assert not Image.open(io.BytesIO(stored.content)).getexif()  # GPS and EXIF removed
    assert events(client, complaint["id"])[-1] == "RESOLUTION_EVIDENCE_UPLOADED"
    # It's not part of the original evidence the letter refers to.
    detail = client.get(f"{API}/complaints/{complaint['id']}").json()
    assert sum(1 for e in detail["evidence"] if e["evidence_type"] == "ORIGINAL") == 1


def test_after_photo_rejections(client: TestClient, db: Session, demo_directory: None) -> None:
    complaint = claimed_fixed(client, db)
    same = upload_after(client, complaint["id"], make_image())  # identical to the original
    assert same.status_code == 409
    assert "same photo as before" in same.json()["error"]["message"]
    not_image = client.post(
        f"{API}/complaints/{complaint['id']}/followup-evidence",
        files={"file": ("x.jpg", b"not an image at all", "image/jpeg")},
        headers=csrf_headers(client),
    )
    assert not_image.status_code == 400
    for seed in range(1, 6):
        assert upload_after(client, complaint["id"], new_photo(seed)).status_code == 201
    sixth = upload_after(client, complaint["id"], new_photo(9))
    assert sixth.status_code == 422 and "at most 5" in sixth.json()["error"]["message"]


# ── The AI comparison is advice ─────────────────────────────────────────────


def test_ai_comparison_is_recorded_but_changes_nothing(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    review = checked(client, complaint["id"])
    assert review["ai_status"] == "SUCCEEDED" and review["is_mock"] is True
    assert review["assessment"]["assessment"] == "APPEARS_RESOLVED"
    assert review["cautions"] == [ALWAYS]
    assert review["decision"] == "PENDING"
    assert review["original_evidence"]["evidence_type"] == "ORIGINAL"
    assert status_of(client, complaint["id"]) == "RESOLVED_PENDING_VERIFICATION"  # unchanged
    analysis = db.scalar(select(AIAnalysis).where(AIAnalysis.analysis_type == "RESOLUTION"))
    assert analysis is not None and analysis.prompt_version == "resolution.v1"
    assert str(analysis.evidence_id) == review["followup_evidence"]["id"]
    assert events(client, complaint["id"])[-1] == "RESOLUTION_ASSESSED"


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("different_place", "different places"),
        ("unsure", "couldn't tell whether both photos"),
        ("partial", "may be incomplete"),
        ("not_resolved", "may still be there"),
    ],
)
def test_uncertain_comparisons_come_with_warnings(
    client: TestClient, db: Session, demo_directory: None, ai, scenario: str, expected: str
) -> None:
    complaint = claimed_fixed(client, db)
    ai.resolution_scenario = scenario
    review = checked(client, complaint["id"])
    assert any(expected in note for note in review["cautions"])


@pytest.mark.parametrize("scenario", ["failure", "invalid"])
def test_ai_failure_leaves_the_citizen_in_charge(
    client: TestClient, db: Session, demo_directory: None, ai, scenario: str
) -> None:
    complaint = claimed_fixed(client, db)
    ai.scenario = scenario
    review = checked(client, complaint["id"])
    assert review["ai_status"] == "FAILED" and review["assessment"] is None
    assert "compare the two photos yourself" in review["cautions"][0]
    assert "AI_ANALYSIS_FAILED" in events(client, complaint["id"])

    # Asking again retries the AI on the same check.
    ai.scenario = "pothole"
    again = review_for(client, complaint["id"], review["followup_evidence"]["id"]).json()
    assert again["id"] == review["id"] and again["ai_status"] == "SUCCEEDED"


def test_decision_works_without_the_ai(
    client: TestClient, db: Session, demo_directory: None, ai
) -> None:
    complaint = claimed_fixed(client, db)
    ai.scenario = "failure"
    review = checked(client, complaint["id"])
    assert decide(client, review["id"], "CONFIRMED_RESOLVED").status_code == 200
    assert status_of(client, complaint["id"]) == "VERIFIED_RESOLVED"


def test_only_follow_up_photos_of_this_complaint_can_be_compared(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    detail = client.get(f"{API}/complaints/{complaint['id']}").json()
    original = detail["evidence"][0]["id"]
    assert review_for(client, complaint["id"], original).status_code == 422
    assert review_for(client, complaint["id"], str(uuid.uuid4())).status_code == 404


# ── Confirm ─────────────────────────────────────────────────────────────────


def test_confirming_a_claimed_repair_verifies_the_complaint(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    review = checked(client, complaint["id"])
    response = decide(client, review["id"], "CONFIRMED_RESOLVED", notes="  Smooth road now.  ")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"] == "CONFIRMED_RESOLVED"
    assert body["citizen_notes"] == "Smooth road now." and body["decided_at"]
    assert status_of(client, complaint["id"]) == "VERIFIED_RESOLVED"
    assert events(client, complaint["id"])[-1] == "RESOLUTION_CONFIRMED"
    stats = client.get(f"{API}/dashboard/summary").json()["stats"]
    assert stats["verified_resolutions"] == 1
    actions = client.get(f"{API}/complaints/{complaint['id']}").json()["available_actions"]
    assert "reopen" in actions and "verify" not in actions


def test_the_citizen_must_say_they_checked(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    review = checked(client, complaint["id"])
    url = f"{API}/resolution-reviews/{review['id']}/decision"
    headers = csrf_headers(client)
    for payload in (
        {"decision": "CONFIRMED_RESOLVED"},
        {"decision": "CONFIRMED_RESOLVED", "checked_myself": False},
        {"decision": "FIXED", "checked_myself": True},
        {"decision": "DISPUTED", "checked_myself": True, "notes": "x" * 1001},
    ):
        assert client.post(url, json=payload, headers=headers).status_code == 422
    assert status_of(client, complaint["id"]) == "RESOLVED_PENDING_VERIFICATION"


def test_the_citizen_can_disagree_with_the_ai(
    client: TestClient, db: Session, demo_directory: None, ai
) -> None:
    complaint = claimed_fixed(client, db)
    ai.resolution_scenario = "not_resolved"
    review = checked(client, complaint["id"])
    decide(client, review["id"], "CONFIRMED_RESOLVED")
    assert status_of(client, complaint["id"]) == "VERIFIED_RESOLVED"


def test_a_fix_found_before_the_department_replies_can_be_confirmed(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = submitted_complaint(client, db)
    assert len(monitoring_of(client, complaint["id"])["response_due_at"] or "") > 0
    review = checked(client, complaint["id"])
    assert decide(client, review["id"], "CONFIRMED_RESOLVED").status_code == 200
    assert status_of(client, complaint["id"]) == "VERIFIED_RESOLVED"
    timeline = events(client, complaint["id"])
    assert timeline[-3:] == ["FOLLOWUPS_STOPPED", "STATUS_CHANGED", "RESOLUTION_CONFIRMED"]
    pending = db.scalars(
        select(ScheduledAction).where(ScheduledAction.execution_status == "PENDING")
    ).all()
    assert pending == []  # no more reminders for a fixed problem


# ── Dispute and reopen ──────────────────────────────────────────────────────


def test_disputing_reopens_and_drafts_a_message_for_approval(
    client: TestClient, db: Session, demo_directory: None, ai, email
) -> None:
    complaint = claimed_fixed(client, db)
    review = checked(client, complaint["id"])
    response = decide(client, review["id"], "DISPUTED", notes="The hole is still there.")
    assert response.json()["decision"] == "DISPUTED"
    assert status_of(client, complaint["id"]) == "REOPENED"
    assert "RESOLUTION_DISPUTED" in events(client, complaint["id"])

    state = monitoring_of(client, complaint["id"])
    notice = state["open_followup"]
    assert notice["delivery_status"] == "DRAFT" and notice["followup_number"] is None
    assert notice["subject"].startswith("Not resolved:")
    assert "The hole is still there." in notice["body"]
    assert "the problem was still there" in notice["body"]
    assert len(email.sent) == 1  # nothing sent without approval

    approved = client.post(
        f"{API}/communications/{notice['id']}/approve",
        json={"confirm": True, "content_sha256": state["open_followup_sha256"]},
        headers=csrf_headers(client),
    )
    assert approved.status_code == 200, approved.text
    sent = send(client, notice["id"]).json()
    assert sent["delivery_status"] == "SIMULATED_SENT" and len(email.sent) == 2
    after = monitoring_of(client, complaint["id"])
    assert after["followups_sent"] == 0  # the notice doesn't use up the reminder limit
    assert after["response_due_at"] is not None  # monitoring restarted

    # If the department stays silent, reminders start again at number 1.
    run_worker(db, ai, email, days=8)
    assert monitoring_of(client, complaint["id"])["open_followup"]["followup_number"] == 1


def test_a_repair_can_only_be_disputed_after_it_was_claimed(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = submitted_complaint(client, db)
    review = checked(client, complaint["id"])
    response = decide(client, review["id"], "DISPUTED")
    assert response.status_code == 409
    assert status_of(client, complaint["id"]) == "SUBMITTED"


def test_reopening_after_the_problem_comes_back(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    review = checked(client, complaint["id"])
    decide(client, review["id"], "CONFIRMED_RESOLVED")
    url = f"{API}/complaints/{complaint['id']}/reopen"
    headers = csrf_headers(client)
    assert client.post(url, json={}, headers=headers).status_code == 422  # must confirm
    response = client.post(url, json={"checked_myself": True}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REOPENED"
    notice = monitoring_of(client, complaint["id"])["open_followup"]
    assert "had come back" in notice["body"]
    assert events(client, complaint["id"])[-2:] == ["COMPLAINT_REOPENED", "FOLLOWUP_SUGGESTED"]
    # Reopening twice isn't possible.
    assert client.post(url, json={"checked_myself": True}, headers=headers).status_code == 409


def test_a_closed_complaint_can_be_reopened_but_not_checked(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = submitted_complaint(client, db)
    client.post(f"{API}/complaints/{complaint['id']}/close", headers=csrf_headers(client))
    assert upload_after(client, complaint["id"]).status_code == 409
    response = client.post(
        f"{API}/complaints/{complaint['id']}/reopen",
        json={"checked_myself": True},
        headers=csrf_headers(client),
    )
    assert response.json()["status"] == "REOPENED"


def test_an_open_complaint_cannot_be_reopened(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = submitted_complaint(client, db)
    response = client.post(
        f"{API}/complaints/{complaint['id']}/reopen",
        json={"checked_myself": True},
        headers=csrf_headers(client),
    )
    assert response.status_code == 409


# ── Duplicates and the audit trail ──────────────────────────────────────────


def test_the_same_decision_twice_counts_once_and_a_change_of_mind_is_refused(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    review = checked(client, complaint["id"])
    first = decide(client, review["id"], "CONFIRMED_RESOLVED")
    second = decide(client, review["id"], "CONFIRMED_RESOLVED")
    assert first.status_code == second.status_code == 200
    assert events(client, complaint["id"]).count("RESOLUTION_CONFIRMED") == 1
    changed = decide(client, review["id"], "DISPUTED")
    assert changed.status_code == 409
    assert status_of(client, complaint["id"]) == "VERIFIED_RESOLVED"


def test_a_newer_photo_replaces_an_undecided_check(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    first = checked(client, complaint["id"], new_photo(1))
    second = checked(client, complaint["id"], new_photo(2))
    assert decide(client, first["id"], "CONFIRMED_RESOLVED").status_code == 409
    history = client.get(f"{API}/complaints/{complaint['id']}/resolution-reviews").json()
    assert [r["id"] for r in history] == [first["id"], second["id"]]  # oldest first, kept
    assert [r["decision"] for r in history] == ["SUPERSEDED", "PENDING"]
    assert decide(client, second["id"], "DISPUTED").status_code == 200

    # A dispute is followed by a new claim and a new check: the history keeps growing.
    simulate(client, complaint["id"], "resolved")
    third = checked(client, complaint["id"], new_photo(3))
    decide(client, third["id"], "CONFIRMED_RESOLVED")
    history = client.get(f"{API}/complaints/{complaint['id']}/resolution-reviews").json()
    assert [r["decision"] for r in history] == ["SUPERSEDED", "DISPUTED", "CONFIRMED_RESOLVED"]


def test_the_database_keeps_reviews_consistent(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    review = checked(client, complaint["id"])
    row = db.get(ResolutionReview, uuid.UUID(review["id"]))
    assert row is not None
    row.decision = "CONFIRMED_RESOLVED"  # a decision without a time...
    with pytest.raises(IntegrityError):
        db.flush()  # ...is refused by the database
    db.rollback()


# ── Ownership ───────────────────────────────────────────────────────────────


def test_other_users_cannot_see_or_decide(
    client: TestClient, other_client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    review = checked(client, complaint["id"])
    cid = complaint["id"]
    headers = csrf_headers(other_client)

    assert other_client.get(f"{API}/complaints/{cid}/resolution-reviews").status_code == 404
    assert other_client.get(review["followup_evidence"]["url"]).status_code == 404
    upload = other_client.post(
        f"{API}/complaints/{cid}/followup-evidence",
        files={"file": ("a.jpg", new_photo(7), "image/jpeg")},
        headers=headers,
    )
    assert upload.status_code == 404
    assert (
        other_client.post(
            f"{API}/complaints/{cid}/resolution-reviews",
            json={"evidence_id": review["followup_evidence"]["id"]},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        other_client.post(
            f"{API}/resolution-reviews/{review['id']}/decision",
            json={"decision": "CONFIRMED_RESOLVED", "checked_myself": True},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        other_client.post(
            f"{API}/complaints/{cid}/reopen", json={"checked_myself": True}, headers=headers
        ).status_code
        == 404
    )
    assert status_of(client, cid) == "RESOLVED_PENDING_VERIFICATION"


def test_original_photo_upload_is_still_draft_only(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    complaint = claimed_fixed(client, db)
    assert upload_photo(client, complaint["id"], new_photo(4)).status_code == 409

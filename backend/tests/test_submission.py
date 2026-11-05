"""Preview, approval, and sending: authorization, provider failures, duplicate-send prevention."""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.integrations.email_providers.base import OutgoingEmail, SendResult
from app.integrations.email_providers.factory import get_email_provider
from app.integrations.email_providers.mock_provider import MockEmailProvider
from app.main import app
from app.modules.authorities.models import Authority
from app.modules.communications.models import Communication
from tests.conftest import create_complaint, csrf_headers, register, upload_photo

API = "/api/v1"
ROADS = "Demo City Roads and Infrastructure Department"


def ready_complaint(client: TestClient, db: Session) -> dict:
    """A complaint with everything needed to submit it to the demo roads department."""
    complaint = create_complaint(
        client,
        title="Deep pothole on Lake Road",
        description="A deep pothole full of water near the school.",
        category="ROAD_POTHOLE",
    )
    assert upload_photo(client, complaint["id"]).status_code == 201
    headers = csrf_headers(client)
    client.patch(
        f"{API}/complaints/{complaint['id']}",
        json={
            "address_line": "45 Lake Road",
            "city": "Demo City",
            "state": "Demo State",
            "confirm_location": True,
        },
        headers=headers,
    )
    roads = db.scalar(select(Authority).where(Authority.name == ROADS))
    assert roads is not None
    client.put(
        f"{API}/complaints/{complaint['id']}/authority",
        json={"authority_id": str(roads.id)},
        headers=headers,
    )
    response = client.post(
        f"{API}/complaints/{complaint['id']}/complaint-draft",
        json={"mode": "template"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return complaint


def preview(client: TestClient, complaint_id: str) -> dict:
    return client.get(f"{API}/complaints/{complaint_id}/submission-preview").json()


def approve(client: TestClient, complaint_id: str, content_hash: str | None = None):
    content_hash = content_hash or preview(client, complaint_id)["content_sha256"]
    return client.post(
        f"{API}/complaints/{complaint_id}/approve",
        json={"confirm": True, "content_sha256": content_hash},
        headers=csrf_headers(client),
    )


def send(client: TestClient, communication_id: str):
    return client.post(
        f"{API}/communications/{communication_id}/send", headers=csrf_headers(client)
    )


def status_of(client: TestClient, complaint_id: str) -> str:
    return client.get(f"{API}/complaints/{complaint_id}").json()["status"]


def events(client: TestClient, complaint_id: str) -> list[str]:
    return [e["event_type"] for e in client.get(f"{API}/complaints/{complaint_id}/timeline").json()]


# ── Preview ─────────────────────────────────────────────────────────────────


def test_preview_shows_exactly_what_will_be_sent(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    body = preview(client, complaint["id"])
    assert body["ready"] is True and body["missing"] == []
    assert body["recipient"] == "roads@demo-city.example"
    assert body["authority"]["is_demo"] is True
    assert body["is_simulated"] is True
    assert body["subject"] and "Dear Sir or Madam" in body["body"]
    assert len(body["attachments"]) == 1
    assert len(body["content_sha256"]) == 64


def test_preview_lists_what_is_missing(client: TestClient, demo_directory: None) -> None:
    register(client)
    complaint = create_complaint(client, title="Only a title")
    body = preview(client, complaint["id"])
    assert body["ready"] is False
    assert {"a photo", "a department", "a complaint letter", "a confirmed location"} <= set(
        body["missing"]
    )
    assert body["content_sha256"] is None


# ── Approval ────────────────────────────────────────────────────────────────


def test_approval_records_what_was_approved(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    content_hash = preview(client, complaint["id"])["content_sha256"]

    response = approve(client, complaint["id"], content_hash)
    assert response.status_code == 200, response.text
    message = response.json()
    assert message["delivery_status"] == "APPROVED"
    assert message["is_simulated"] is True
    assert status_of(client, complaint["id"]) == "PENDING_REVIEW"
    assert events(client, complaint["id"])[-1] == "COMPLAINT_APPROVED"

    row = db.get(Communication, uuid.UUID(message["id"]))
    assert row is not None
    assert row.content_sha256 == content_hash
    assert row.approval_details["content_sha256"] == content_hash  # type: ignore[index]


def test_cannot_approve_incomplete_complaint(client: TestClient, demo_directory: None) -> None:
    register(client)
    complaint = create_complaint(client, title="Only a title")
    response = approve(client, complaint["id"], "0" * 64)
    assert response.status_code == 422


def test_approval_requires_explicit_confirmation(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    content_hash = preview(client, complaint["id"])["content_sha256"]
    response = client.post(
        f"{API}/complaints/{complaint['id']}/approve",
        json={"confirm": False, "content_sha256": content_hash},
        headers=csrf_headers(client),
    )
    assert response.status_code == 422


def test_approval_of_an_outdated_preview_is_refused(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    old_hash = preview(client, complaint["id"])["content_sha256"]
    client.patch(
        f"{API}/complaints/{complaint['id']}",
        json={"draft_subject": "A different subject line"},
        headers=csrf_headers(client),
    )
    response = approve(client, complaint["id"], old_hash)
    assert response.status_code == 409
    assert "changed" in response.json()["error"]["message"]


def test_editing_after_approval_withdraws_it(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    message = approve(client, complaint["id"]).json()

    client.patch(
        f"{API}/complaints/{complaint['id']}",
        json={"draft_body": "Dear Sir or Madam, I have rewritten my complaint about the pothole."},
        headers=csrf_headers(client),
    )
    assert status_of(client, complaint["id"]) == "DRAFT"
    assert "APPROVAL_WITHDRAWN" in events(client, complaint["id"])

    response = send(client, message["id"])
    assert response.status_code == 409  # the old approval can't be used to send

    # Approving again creates a new version and retires the old one.
    new_message = approve(client, complaint["id"]).json()
    assert new_message["id"] != message["id"]
    assert db.get(Communication, uuid.UUID(message["id"])).delivery_status == "SUPERSEDED"  # type: ignore[union-attr]
    assert send(client, message["id"]).status_code == 409


# ── Sending ─────────────────────────────────────────────────────────────────


def test_simulated_send(
    client: TestClient, db: Session, demo_directory: None, email: MockEmailProvider
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    message = approve(client, complaint["id"]).json()

    response = send(client, message["id"])
    assert response.status_code == 200, response.text
    sent = response.json()
    assert sent["delivery_status"] == "SIMULATED_SENT"  # never "SENT" for a simulation
    assert sent["is_simulated"] is True
    assert sent["sent_at"] is not None

    detail = client.get(f"{API}/complaints/{complaint['id']}").json()
    assert detail["status"] == "SUBMITTED"
    assert detail["submitted_at"] is not None
    timeline = client.get(f"{API}/complaints/{complaint['id']}/timeline").json()
    assert [e["event_type"] for e in timeline][-2:] == [
        "SUBMISSION_ATTEMPTED",
        "SUBMISSION_ACCEPTED",
    ]
    assert "No email was sent to a real department" in timeline[-1]["description"]

    assert len(email.sent) == 1
    (outgoing,) = email.sent.values()
    assert outgoing.to == "roads@demo-city.example"
    assert outgoing.attachment_names == ["photo-1"]


def test_sending_twice_sends_once(
    client: TestClient, db: Session, demo_directory: None, email: MockEmailProvider
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    message = approve(client, complaint["id"]).json()
    first = send(client, message["id"]).json()
    second = send(client, message["id"])
    assert second.status_code == 200
    assert second.json()["sent_at"] == first["sent_at"]
    assert second.json()["attempt_count"] == 1
    assert len(email.sent) == 1
    assert events(client, complaint["id"]).count("SUBMISSION_ACCEPTED") == 1


def test_send_while_already_sending_is_refused(
    client: TestClient, db: Session, demo_directory: None, email: MockEmailProvider
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    message = approve(client, complaint["id"]).json()
    db.execute(
        update(Communication)
        .where(Communication.id == uuid.UUID(message["id"]))
        .values(delivery_status="SENDING")
    )
    db.commit()
    response = send(client, message["id"])
    assert response.status_code == 409
    assert len(email.sent) == 0


def test_stuck_sending_can_be_retried(
    client: TestClient, db: Session, demo_directory: None, email: MockEmailProvider
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    message = approve(client, complaint["id"]).json()
    db.execute(
        update(Communication)
        .where(Communication.id == uuid.UUID(message["id"]))
        .values(delivery_status="SENDING", updated_at=utc_now() - timedelta(minutes=30))
    )
    db.commit()
    assert send(client, message["id"]).json()["delivery_status"] == "SIMULATED_SENT"


def test_provider_failure_then_retry(
    client: TestClient, db: Session, demo_directory: None, email: MockEmailProvider
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    message = approve(client, complaint["id"]).json()
    email.scenario = "failure"

    response = send(client, message["id"])
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SUBMISSION_FAILED"
    assert "nothing was delivered" in response.json()["error"]["message"]
    assert status_of(client, complaint["id"]) == "PENDING_REVIEW"  # still approved, not submitted
    assert events(client, complaint["id"])[-1] == "SUBMISSION_FAILED"
    assert db.get(Communication, uuid.UUID(message["id"])).delivery_status == "FAILED"  # type: ignore[union-attr]
    assert len(email.sent) == 0

    email.scenario = "success"
    retried = send(client, message["id"]).json()
    assert retried["delivery_status"] == "SIMULATED_SENT"
    assert retried["attempt_count"] == 2
    assert len(email.sent) == 1


def test_flaky_provider_first_attempt_fails(
    client: TestClient, db: Session, demo_directory: None, email: MockEmailProvider
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    message = approve(client, complaint["id"]).json()
    email.scenario = "flaky"
    assert send(client, message["id"]).status_code == 503
    assert send(client, message["id"]).status_code == 200
    assert len(email.sent) == 1


def test_submitted_complaint_can_no_longer_be_changed(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    send(client, approve(client, complaint["id"]).json()["id"])
    headers = csrf_headers(client)
    assert (
        client.patch(
            f"{API}/complaints/{complaint['id']}", json={"title": "Changed later"}, headers=headers
        ).status_code
        == 409
    )
    assert approve(client, complaint["id"], "0" * 64).status_code == 409


# ── Authorization ───────────────────────────────────────────────────────────


def test_other_user_cannot_preview_approve_send_or_read(
    client: TestClient,
    other_client: TestClient,
    db: Session,
    demo_directory: None,
    email: MockEmailProvider,
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    content_hash = preview(client, complaint["id"])["content_sha256"]
    message = approve(client, complaint["id"], content_hash).json()

    assert (
        other_client.get(f"{API}/complaints/{complaint['id']}/submission-preview").status_code
        == 404
    )
    assert approve(other_client, complaint["id"], content_hash).status_code == 404
    assert send(other_client, message["id"]).status_code == 404
    assert other_client.get(f"{API}/complaints/{complaint['id']}/communications").status_code == 404
    assert len(email.sent) == 0


def test_communication_history_is_chronological(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    first = approve(client, complaint["id"]).json()
    client.patch(
        f"{API}/complaints/{complaint['id']}",
        json={"draft_subject": "Second version of the subject"},
        headers=csrf_headers(client),
    )
    second = approve(client, complaint["id"]).json()
    send(client, second["id"])
    history = client.get(f"{API}/complaints/{complaint['id']}/communications").json()
    assert [m["id"] for m in history] == [first["id"], second["id"]]
    assert [m["delivery_status"] for m in history] == ["SUPERSEDED", "SIMULATED_SENT"]


# ── Never pretend a simulation was a real delivery ──────────────────────────


def test_database_refuses_simulated_message_marked_as_sent(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    message = approve(client, complaint["id"]).json()
    with pytest.raises(IntegrityError):
        db.execute(
            update(Communication)
            .where(Communication.id == uuid.UUID(message["id"]))
            .values(delivery_status="SENT")
        )
        db.flush()


class FakeRealProvider:
    """Stands in for a future real email provider (is_simulated = False)."""

    name = "fake-real"
    is_simulated = False

    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []

    def send(self, email: OutgoingEmail) -> SendResult:
        self.sent.append(email)
        return SendResult(provider_message_id="real-1")


def test_real_provider_is_blocked_for_demo_departments(
    client: TestClient, db: Session, demo_directory: None
) -> None:
    register(client)
    complaint = ready_complaint(client, db)
    real = FakeRealProvider()
    app.dependency_overrides[get_email_provider] = lambda: real
    message = approve(client, complaint["id"]).json()
    assert message["is_simulated"] is False

    response = send(client, message["id"])  # ALLOW_REAL_SUBMISSIONS is false
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "REAL_SUBMISSION_BLOCKED"
    assert real.sent == []
    assert status_of(client, complaint["id"]) == "PENDING_REVIEW"

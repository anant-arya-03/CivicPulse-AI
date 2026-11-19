import pytest
from pydantic import SecretStr

from app.core.config import get_settings
from tests.conftest import register
from tests.test_submission import approve, ready_complaint, send, status_of

INBOX = "/api/v1/department/reports"
CODE = "local-demo-access-code-for-tests"
OPERATOR = {"Authorization": f"Bearer {CODE}"}


@pytest.fixture
def portal(monkeypatch, demo_directory, other_client):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_simulation", True)
    monkeypatch.setattr(settings, "department_access_code", SecretStr(CODE))
    monkeypatch.setattr(settings, "department_authority_email", "roads@demo-city.example")
    other_client.cookies.clear()  # The portal sends its bearer code without citizen cookies.


def test_approval_send_and_department_repair_update(client, other_client, db, portal):
    register(client)
    complaint = ready_complaint(client, db)
    complaint_id = complaint["id"]
    action = f"{INBOX}/{complaint_id}/status"

    assert other_client.get(INBOX).status_code == 401
    assert other_client.get(INBOX, headers=OPERATOR).json()["reports"] == []
    approved = approve(client, complaint_id).json()
    evidence_id = approved["attachments"][0]["evidence_id"]
    attachment = f"{INBOX}/{complaint_id}/attachments/{evidence_id}"
    assert other_client.get(INBOX, headers=OPERATOR).json()["reports"] == []
    assert other_client.get(attachment, headers=OPERATOR).status_code == 404
    assert (
        other_client.post(action, headers=OPERATOR, json={"update": "repair_complete"}).status_code
        == 404
    )
    assert send(client, approved["id"]).status_code == 200

    inbox = other_client.get(INBOX, headers=OPERATOR).json()
    assert inbox["reports"][0]["id"] == complaint_id
    assert inbox["reports"][0]["body"] == approved["body"]
    assert inbox["reports"][0]["attachment_ids"] == [evidence_id]
    photo = other_client.get(attachment, headers=OPERATOR)
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/jpeg"
    assert other_client.get(attachment).status_code == 401
    assert (
        other_client.post(action, headers=OPERATOR, json={"update": "verify_repair"}).status_code
        == 422
    )
    started = other_client.post(action, headers=OPERATOR, json={"update": "start_work"})
    assert started.json()["status"] == "IN_PROGRESS"
    for _ in range(2):
        completed = other_client.post(action, headers=OPERATOR, json={"update": "repair_complete"})
        assert completed.json()["status"] == "RESOLVED_PENDING_VERIFICATION"
    assert status_of(client, complaint_id) == "RESOLVED_PENDING_VERIFICATION"
    history = client.get(f"/api/v1/complaints/{complaint_id}/communications").json()
    repairs = [item for item in history if item["reply_kind"] == "RESOLVED_CLAIM"]
    assert len(repairs) == 1
    assert repairs[0]["reply_kind_source"] == "DEPARTMENT"
    assert repairs[0]["is_simulated"]


def test_operator_cannot_access_other_departments(client, other_client, db, portal, monkeypatch):
    register(client)
    complaint_id = ready_complaint(client, db)["id"]
    assert send(client, approve(client, complaint_id).json()["id"]).status_code == 200
    monkeypatch.setattr(get_settings(), "department_authority_email", "waste@demo-city.example")
    assert other_client.get(INBOX, headers=OPERATOR).json()["reports"] == []
    response = other_client.post(
        f"{INBOX}/{complaint_id}/status", headers=OPERATOR, json={"update": "repair_complete"}
    )
    assert response.status_code == 404
    assert status_of(client, complaint_id) == "SUBMITTED"


def test_portal_is_unavailable_outside_simulation(other_client, portal, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_simulation", False)
    assert other_client.get(INBOX, headers=OPERATOR).status_code == 404

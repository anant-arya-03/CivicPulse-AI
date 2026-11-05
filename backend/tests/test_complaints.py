import re
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.complaints.models import Complaint
from tests.conftest import create_complaint, csrf_headers, register, upload_photo

API = "/api/v1/complaints"


def set_status(db: Session, complaint_id: str, status: str) -> None:
    """Jump a complaint to a later status directly (the API for it arrives in later milestones)."""
    complaint = db.get(Complaint, uuid.UUID(complaint_id))
    assert complaint is not None
    complaint.status = status
    db.commit()


def event_types(client: TestClient, complaint_id: str) -> list[str]:
    return [e["event_type"] for e in client.get(f"{API}/{complaint_id}/timeline").json()]


# ── Create & read ───────────────────────────────────────────────────────────


def test_create_draft(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)

    assert complaint["status"] == "DRAFT"
    assert re.fullmatch(r"CP-\d{4}-\d{6}", complaint["public_reference"])
    assert complaint["evidence"] == []
    assert set(complaint["available_actions"]) == {"edit", "add_photo", "cancel"}
    assert event_types(client, complaint["id"]) == ["COMPLAINT_CREATED"]


def test_create_with_initial_fields(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client, title="Broken streetlight", category="BROKEN_STREETLIGHT")
    assert complaint["title"] == "Broken streetlight"
    assert complaint["category"] == "BROKEN_STREETLIGHT"


def test_references_are_unique(client: TestClient) -> None:
    register(client)
    refs = {create_complaint(client)["public_reference"] for _ in range(3)}
    assert len(refs) == 3


def test_create_requires_login(client: TestClient) -> None:
    assert client.post(API, json={}).status_code == 401


def test_get_complaint(client: TestClient) -> None:
    register(client)
    created = create_complaint(client, title="Pothole near school")
    response = client.get(f"{API}/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Pothole near school"


def test_get_unknown_complaint_is_404(client: TestClient) -> None:
    register(client)
    assert client.get(f"{API}/{uuid.uuid4()}").status_code == 404


# ── Ownership: another user's complaint always looks like it doesn't exist ──


def test_other_users_complaint_is_hidden(client: TestClient, other_client: TestClient) -> None:
    register(client)
    mine = create_complaint(client, title="My private complaint")

    for method, path, body in [
        ("GET", f"{API}/{mine['id']}", None),
        ("GET", f"{API}/{mine['id']}/timeline", None),
        ("PATCH", f"{API}/{mine['id']}", {"title": "Hijacked title"}),
        ("POST", f"{API}/{mine['id']}/cancel", None),
        ("POST", f"{API}/{mine['id']}/close", None),
    ]:
        response = other_client.request(method, path, json=body, headers=csrf_headers(other_client))
        assert response.status_code == 404, (method, path)
        assert response.json()["error"]["code"] == "NOT_FOUND"

    assert other_client.get(API).json()["total"] == 0
    assert client.get(f"{API}/{mine['id']}").json()["title"] == "My private complaint"


# ── Update draft ────────────────────────────────────────────────────────────


def test_update_draft_fields_and_records_event(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    response = client.patch(
        f"{API}/{complaint['id']}",
        json={
            "title": "  Deep   pothole on Lake Road ",
            "description": "Large pothole.\nCars swerve around it.",
            "category": "ROAD_POTHOLE",
            "severity": "HIGH",
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Deep pothole on Lake Road"
    assert body["description"] == "Large pothole.\nCars swerve around it."  # line breaks kept
    assert body["category"] == "ROAD_POTHOLE"
    assert event_types(client, complaint["id"]) == ["COMPLAINT_CREATED", "DETAILS_UPDATED"]


def test_update_without_changes_records_no_event(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client, title="Same title here")
    client.patch(
        f"{API}/{complaint['id']}", json={"title": "Same title here"}, headers=csrf_headers(client)
    )
    assert event_types(client, complaint["id"]) == ["COMPLAINT_CREATED"]


def test_update_validation(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    for bad in [
        {"title": "Hi"},  # too short
        {"category": "NOT_A_CATEGORY"},
        {"latitude": 12.5},  # longitude missing
        {"latitude": 95, "longitude": 10},  # out of range
        {"country": "India"},  # must be a 2-letter code
        {"observed_at": "2999-01-01T00:00:00Z"},  # in the future
    ]:
        response = client.patch(f"{API}/{complaint['id']}", json=bad, headers=csrf_headers(client))
        assert response.status_code == 422, bad


def test_confirm_location(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    response = client.patch(
        f"{API}/{complaint['id']}",
        json={
            "address_line": "45 Lake Road",
            "locality": "Lakeside",
            "city": "Demo City",
            "country": "xx",
            "latitude": 0.0151,
            "longitude": 0.0098,
            "confirm_location": True,
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["location_confirmed_at"] is not None
    assert body["country"] == "XX"
    assert body["latitude"] == 0.0151
    assert event_types(client, complaint["id"])[-1] == "LOCATION_CONFIRMED"

    # Changing the address afterwards means it must be confirmed again.
    response = client.patch(
        f"{API}/{complaint['id']}", json={"city": "Other City"}, headers=csrf_headers(client)
    )
    assert response.json()["location_confirmed_at"] is None


def test_confirm_location_requires_address_and_city(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    response = client.patch(
        f"{API}/{complaint['id']}",
        json={"locality": "Lakeside", "confirm_location": True},
        headers=csrf_headers(client),
    )
    assert response.status_code == 422
    # Nothing was saved because the whole request was rejected.
    assert client.get(f"{API}/{complaint['id']}").json()["locality"] is None


def test_same_coordinates_are_not_reported_as_changed(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client, latitude=12.971599, longitude=77.594566)
    client.patch(
        f"{API}/{complaint['id']}",
        json={"latitude": 12.971599, "longitude": 77.594566},
        headers=csrf_headers(client),
    )
    assert event_types(client, complaint["id"]) == ["COMPLAINT_CREATED"]


def test_cannot_edit_after_submission(client: TestClient, db: Session) -> None:
    register(client)
    complaint = create_complaint(client)
    set_status(db, complaint["id"], "SUBMITTED")
    response = client.patch(
        f"{API}/{complaint['id']}", json={"title": "Too late to edit"}, headers=csrf_headers(client)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


# ── Cancel & close (status transitions through the API) ─────────────────────


def test_cancel_draft(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    response = client.post(f"{API}/{complaint['id']}/cancel", headers=csrf_headers(client))
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert response.json()["available_actions"] == []

    timeline = client.get(f"{API}/{complaint['id']}/timeline").json()
    assert timeline[-1]["event_type"] == "COMPLAINT_CANCELLED"
    assert (timeline[-1]["previous_status"], timeline[-1]["new_status"]) == ("DRAFT", "CANCELLED")


def test_cancel_twice_is_rejected(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    client.post(f"{API}/{complaint['id']}/cancel", headers=csrf_headers(client))
    response = client.post(f"{API}/{complaint['id']}/cancel", headers=csrf_headers(client))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


def test_close_draft_is_rejected(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    response = client.post(f"{API}/{complaint['id']}/close", headers=csrf_headers(client))
    assert response.status_code == 409
    assert "cannot be changed to closed" in response.json()["error"]["message"]


def test_close_submitted_complaint(client: TestClient, db: Session) -> None:
    register(client)
    complaint = create_complaint(client)
    set_status(db, complaint["id"], "SUBMITTED")
    assert "close" in client.get(f"{API}/{complaint['id']}").json()["available_actions"]

    response = client.post(f"{API}/{complaint['id']}/close", headers=csrf_headers(client))
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


def test_cancelled_complaint_cannot_be_closed(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    client.post(f"{API}/{complaint['id']}/cancel", headers=csrf_headers(client))
    assert (
        client.post(f"{API}/{complaint['id']}/close", headers=csrf_headers(client)).status_code
        == 409
    )


# ── List: search, filters, sort, pagination ─────────────────────────────────


def _seed_list(client: TestClient, db: Session) -> dict[str, str]:
    ids = {
        "pothole": create_complaint(
            client, title="Pothole on Market Street", category="ROAD_POTHOLE", city="Demo City"
        )["id"],
        "light": create_complaint(
            client, title="Streetlight not working", category="BROKEN_STREETLIGHT"
        )["id"],
        "garbage": create_complaint(
            client,
            title="Garbage overflowing",
            category="GARBAGE_OVERFLOW",
            description="Bins near the 100% full market",
        )["id"],
    }
    set_status(db, ids["light"], "SUBMITTED")
    return ids


def _titles(client: TestClient, query: str = "") -> list[str]:
    return [item["title"] for item in client.get(f"{API}?{query}").json()["items"]]


def test_list_newest_first_by_default(client: TestClient, db: Session) -> None:
    register(client)
    _seed_list(client, db)
    assert _titles(client) == [
        "Garbage overflowing",
        "Streetlight not working",
        "Pothole on Market Street",
    ]
    assert _titles(client, "sort=created_at")[0] == "Pothole on Market Street"


def test_list_search(client: TestClient, db: Session) -> None:
    register(client)
    _seed_list(client, db)
    assert _titles(client, "search=market") == ["Garbage overflowing", "Pothole on Market Street"]
    assert _titles(client, "search=STREETLIGHT") == ["Streetlight not working"]
    assert _titles(client, "search=demo%20city") == ["Pothole on Market Street"]
    # "%" is matched literally, not as a wildcard.
    assert _titles(client, "search=100%25") == ["Garbage overflowing"]
    assert _titles(client, "search=nothing-matches") == []


def test_list_search_by_reference(client: TestClient, db: Session) -> None:
    register(client)
    ids = _seed_list(client, db)
    reference = client.get(f"{API}/{ids['light']}").json()["public_reference"]
    assert _titles(client, f"search={reference}") == ["Streetlight not working"]


def test_list_filters(client: TestClient, db: Session) -> None:
    register(client)
    _seed_list(client, db)
    assert _titles(client, "category=ROAD_POTHOLE") == ["Pothole on Market Street"]
    assert _titles(client, "status=SUBMITTED") == ["Streetlight not working"]
    assert _titles(client, "status=DRAFT&category=BROKEN_STREETLIGHT") == []
    assert client.get(f"{API}?status=NOPE").status_code == 422


def test_list_pagination(client: TestClient) -> None:
    register(client)
    for i in range(5):
        create_complaint(client, title=f"Complaint number {i}")

    page1 = client.get(f"{API}?page=1&page_size=2").json()
    page3 = client.get(f"{API}?page=3&page_size=2").json()
    assert (page1["total"], page1["total_pages"], len(page1["items"])) == (5, 3, 2)
    assert [i["title"] for i in page1["items"]] == ["Complaint number 4", "Complaint number 3"]
    assert [i["title"] for i in page3["items"]] == ["Complaint number 0"]
    assert client.get(f"{API}?page_size=500").status_code == 422


def test_list_item_includes_thumbnail(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    evidence = upload_photo(client, complaint["id"]).json()
    item = client.get(API).json()["items"][0]
    assert item["thumbnail_url"] == f"/api/v1/evidence/{evidence['id']}/file"


# ── Dashboard ───────────────────────────────────────────────────────────────


def test_dashboard_summary(client: TestClient, db: Session) -> None:
    register(client)
    empty = client.get("/api/v1/dashboard/summary").json()
    assert empty["stats"] == {
        "total": 0,
        "drafts": 0,
        "active": 0,
        "pending_responses": 0,
        "verified_resolutions": 0,
    }

    ids = _seed_list(client, db)  # 2 drafts + 1 submitted
    cancelled = create_complaint(client, title="Changed my mind")
    client.post(f"{API}/{cancelled['id']}/cancel", headers=csrf_headers(client))
    set_status(db, ids["garbage"], "VERIFIED_RESOLVED")

    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["stats"] == {
        "total": 3,  # cancelled complaints are not counted
        "drafts": 1,
        "active": 1,
        "pending_responses": 1,
        "verified_resolutions": 1,
    }
    assert {c["title"] for c in summary["recent_complaints"]} == {
        "Pothole on Market Street",
        "Streetlight not working",
        "Garbage overflowing",
        "Changed my mind",
    }
    assert summary["recent_activity"][0]["event_type"] == "COMPLAINT_CANCELLED"
    assert summary["recent_activity"][0]["complaint_title"] == "Changed my mind"


def test_dashboard_only_counts_own_complaints(
    client: TestClient, other_client: TestClient, db: Session
) -> None:
    register(client)
    create_complaint(client)
    stats = other_client.get("/api/v1/dashboard/summary").json()
    assert stats["stats"]["total"] == 0
    assert stats["recent_activity"] == []
    assert db.scalar(select(Complaint).limit(1)) is not None

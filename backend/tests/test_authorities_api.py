import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.authorities.models import Authority
from app.modules.authorities.schemas import AuthorityImport
from app.modules.authorities.service import import_authorities
from tests.conftest import create_complaint, csrf_headers, register

API = "/api/v1"


def authority_id(db: Session, name: str) -> str:
    authority = db.scalar(select(Authority).where(Authority.name == name))
    assert authority is not None
    return str(authority.id)


def complaint_in_demo_city(
    client: TestClient, category: str = "ROAD_POTHOLE", **extra: object
) -> dict:
    return create_complaint(
        client, category=category, city="Demo City", state="Demo State", **extra
    )


def choose(client: TestClient, complaint_id: str, chosen: str):
    return client.put(
        f"{API}/complaints/{complaint_id}/authority",
        json={"authority_id": chosen},
        headers=csrf_headers(client),
    )


# ── Directory ───────────────────────────────────────────────────────────────


def test_directory_search(client: TestClient, demo_directory: None) -> None:
    register(client)
    everything = client.get(f"{API}/authorities").json()
    assert len(everything) == 7
    assert all(a["is_demo"] for a in everything)
    assert all(a["official_email"].endswith(".example") for a in everything)

    roads = client.get(f"{API}/authorities?category=ROAD_POTHOLE").json()
    assert {a["name"] for a in roads} == {
        "Demo City Roads and Infrastructure Department",
        "Demo State Public Works Department",
    }
    assert [a["name"] for a in client.get(f"{API}/authorities?q=lighting").json()] == [
        "Demo City Street Lighting Department"
    ]


def test_directory_requires_login(client: TestClient, demo_directory: None) -> None:
    assert client.get(f"{API}/authorities").status_code == 401


# ── Matching for a complaint ────────────────────────────────────────────────


def test_exact_match(client: TestClient, demo_directory: None) -> None:
    register(client)
    complaint = complaint_in_demo_city(client)
    body = client.get(f"{API}/complaints/{complaint['id']}/authority-matches").json()
    assert body["confidence"] == "EXACT"
    assert (
        body["matches"][0]["authority"]["name"] == "Demo City Roads and Infrastructure Department"
    )
    assert body["selected_authority_id"] is None  # matching never selects on its own


def test_uncertain_match_lists_choices(client: TestClient, demo_directory: None) -> None:
    register(client)
    complaint = complaint_in_demo_city(client, category="WATERLOGGING")
    body = client.get(f"{API}/complaints/{complaint['id']}/authority-matches").json()
    assert body["confidence"] == "PARTIAL"
    assert len(body["matches"]) == 2


def test_no_match_elsewhere(client: TestClient, demo_directory: None) -> None:
    register(client)
    complaint = create_complaint(client, category="ROAD_POTHOLE", city="Pune", country="IN")
    assert (
        client.get(f"{API}/complaints/{complaint['id']}/authority-matches").json()["confidence"]
        == "NONE"
    )


def test_matching_needs_category_and_city(client: TestClient, demo_directory: None) -> None:
    register(client)
    complaint = create_complaint(client)
    response = client.get(f"{API}/complaints/{complaint['id']}/authority-matches")
    assert response.status_code == 422


# ── Choosing a department ───────────────────────────────────────────────────


def test_select_department(client: TestClient, demo_directory: None, db: Session) -> None:
    register(client)
    complaint = complaint_in_demo_city(client)
    roads = authority_id(db, "Demo City Roads and Infrastructure Department")
    response = choose(client, complaint["id"], roads)
    assert response.status_code == 200
    assert response.json()["authority"]["id"] == roads
    timeline = client.get(f"{API}/complaints/{complaint['id']}/timeline").json()
    assert timeline[-1]["event_type"] == "AUTHORITY_SELECTED"
    assert "(demo directory entry)" in timeline[-1]["description"]


def test_cannot_select_department_that_doesnt_handle_the_issue(
    client: TestClient, demo_directory: None, db: Session
) -> None:
    register(client)
    complaint = complaint_in_demo_city(client)
    lights = authority_id(db, "Demo City Street Lighting Department")
    response = choose(client, complaint["id"], lights)
    assert response.status_code == 422
    assert "doesn't handle" in response.json()["error"]["message"]


def test_cannot_select_unknown_or_inactive_department(
    client: TestClient, demo_directory: None, db: Session
) -> None:
    register(client)
    complaint = complaint_in_demo_city(client)
    assert choose(client, complaint["id"], str(uuid.uuid4())).status_code == 404

    roads = db.scalar(select_authority_by_name("Demo City Roads and Infrastructure Department"))
    assert roads is not None
    roads.active = False
    db.commit()
    assert choose(client, complaint["id"], str(roads.id)).status_code == 404


def select_authority_by_name(name: str):
    from sqlalchemy import select as sql_select

    return sql_select(Authority).where(Authority.name == name)


def test_changing_category_clears_an_incompatible_department(
    client: TestClient, demo_directory: None, db: Session
) -> None:
    register(client)
    complaint = complaint_in_demo_city(client)
    choose(
        client, complaint["id"], authority_id(db, "Demo City Roads and Infrastructure Department")
    )
    response = client.patch(
        f"{API}/complaints/{complaint['id']}",
        json={"category": "BROKEN_STREETLIGHT"},
        headers=csrf_headers(client),
    )
    assert response.json()["authority"] is None


def test_other_user_cannot_route_my_complaint(
    client: TestClient, other_client: TestClient, demo_directory: None, db: Session
) -> None:
    register(client)
    complaint = complaint_in_demo_city(client)
    roads = authority_id(db, "Demo City Roads and Infrastructure Department")
    assert (
        other_client.get(f"{API}/complaints/{complaint['id']}/authority-matches").status_code == 404
    )
    assert choose(other_client, complaint["id"], roads).status_code == 404


# ── Source-backed directory rules ───────────────────────────────────────────


def test_database_rejects_unsourced_real_records(db: Session) -> None:
    db.add(
        Authority(
            name="Unsourced Department",
            jurisdiction="Somewhere",
            jurisdiction_level="CITY",
            country="IN",
            supported_categories=["ROAD_POTHOLE"],
            official_email="help@city.gov.in",
            is_demo=False,  # real, but no source_url / verified_at
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


VALID_IMPORT = {
    "name": "Ward 5 Roads Office",
    "jurisdiction": "Ward 5, Sample Town",
    "jurisdiction_level": "WARD",
    "city": "Sample Town",
    "state": "Sample State",
    "country": "IN",
    "supported_categories": ["ROAD_POTHOLE"],
    "official_email": "roads-ward5@sampletown.gov.in",
    "source_url": "https://sampletown.gov.in/contact",
    "verified_at": date.today().isoformat(),
}


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"source_url": "http://sampletown.gov.in/contact"}, "https"),
        ({"verified_at": (date.today() + timedelta(days=3)).isoformat()}, "future"),
        ({"verified_at": (date.today() - timedelta(days=400)).isoformat()}, "over a year"),
        ({"official_email": "roads@city.example"}, "Reserved"),
        ({"supported_categories": ["VOLCANO"]}, "Input should be"),
        ({"is_demo": True}, "Extra inputs"),
    ],
)
def test_import_validation(change: dict, problem: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuthorityImport.model_validate({**VALID_IMPORT, **change})
    assert problem in str(exc_info.value)


def test_import_creates_a_source_backed_real_record(db: Session) -> None:
    import_authorities(db, [AuthorityImport.model_validate(VALID_IMPORT)])
    record = db.scalar(select(Authority).where(Authority.name == "Ward 5 Roads Office"))
    assert record is not None
    assert record.is_demo is False
    assert record.source_url == "https://sampletown.gov.in/contact"
    assert record.verified_at == date.today()

    # Importing again updates instead of duplicating.
    import_authorities(
        db, [AuthorityImport.model_validate({**VALID_IMPORT, "official_phone": "100"})]
    )
    rows = db.scalars(select(Authority).where(Authority.name == "Ward 5 Roads Office")).all()
    assert len(rows) == 1 and rows[0].official_phone == "100"

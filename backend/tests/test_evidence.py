import hashlib
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.storage.local_storage import LocalStorage
from app.modules.complaints.models import Complaint
from app.modules.evidence.models import Evidence
from tests.conftest import create_complaint, csrf_headers, make_image, register, upload_photo


@pytest.fixture()
def complaint(client: TestClient) -> dict:
    register(client)
    return create_complaint(client)


# ── Valid uploads ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("image_format", "mime"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_upload_accepted_formats(
    client: TestClient, complaint: dict, image_format: str, mime: str
) -> None:
    response = upload_photo(client, complaint["id"], make_image(image_format), content_type=mime)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["file_type"] == mime
    assert (body["width"], body["height"]) == (320, 240)
    assert body["url"] == f"/api/v1/evidence/{body['id']}/file"


def test_upload_records_event_and_appears_on_complaint(client: TestClient, complaint: dict) -> None:
    evidence = upload_photo(client, complaint["id"]).json()
    detail = client.get(f"/api/v1/complaints/{complaint['id']}").json()
    assert [e["id"] for e in detail["evidence"]] == [evidence["id"]]
    timeline = client.get(f"/api/v1/complaints/{complaint['id']}/timeline").json()
    assert timeline[-1]["event_type"] == "EVIDENCE_UPLOADED"


def test_stored_file_has_no_exif_or_gps(
    client: TestClient, complaint: dict, storage: LocalStorage, db: Session
) -> None:
    original = make_image("JPEG", with_gps_exif=True)
    assert Image.open(io.BytesIO(original)).getexif().get_ifd(0x8825)  # GPS really is there

    evidence_id = upload_photo(client, complaint["id"], original).json()["id"]
    evidence = db.get(Evidence, uuid.UUID(evidence_id))
    assert evidence is not None
    stored = storage.read(evidence.file_storage_key)

    cleaned = Image.open(io.BytesIO(stored))
    assert len(cleaned.getexif()) == 0
    assert "exif" not in cleaned.info
    # The checksum describes the cleaned file that we actually keep.
    assert evidence.checksum == hashlib.sha256(stored).hexdigest()


def test_filename_and_content_type_are_ignored(client: TestClient, complaint: dict) -> None:
    # A real PNG uploaded with a misleading name and type is detected as PNG.
    response = upload_photo(
        client, complaint["id"], make_image("PNG"), filename="x.exe", content_type="text/plain"
    )
    assert response.status_code == 201
    assert response.json()["file_type"] == "image/png"


# ── Rejected uploads ────────────────────────────────────────────────────────


def _assert_rejected(response, status: int = 400) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == "FILE_REJECTED"


def test_rejects_non_image(client: TestClient, complaint: dict) -> None:
    _assert_rejected(upload_photo(client, complaint["id"], b"hello, I am not a photo"))


def test_rejects_disguised_script(client: TestClient, complaint: dict) -> None:
    fake = b"<script>alert('x')</script>" + b"\0" * 200
    _assert_rejected(upload_photo(client, complaint["id"], fake, filename="photo.jpg"))


def test_rejects_unsupported_format(client: TestClient, complaint: dict) -> None:
    response = upload_photo(client, complaint["id"], make_image("GIF"), content_type="image/gif")
    _assert_rejected(response)
    assert "JPEG, PNG, and WebP" in response.json()["error"]["message"]


def test_rejects_truncated_image(client: TestClient, complaint: dict) -> None:
    data = make_image("PNG", (400, 400))
    _assert_rejected(upload_photo(client, complaint["id"], data[: len(data) // 2]))


def test_rejects_empty_file(client: TestClient, complaint: dict) -> None:
    _assert_rejected(upload_photo(client, complaint["id"], b""))


def test_rejects_tiny_image(client: TestClient, complaint: dict) -> None:
    _assert_rejected(upload_photo(client, complaint["id"], make_image("PNG", (10, 10))))


def test_rejects_file_over_size_limit(client: TestClient, complaint: dict) -> None:
    too_big = make_image("PNG") + b"\0" * (get_settings().max_upload_bytes + 1)
    _assert_rejected(upload_photo(client, complaint["id"], too_big), status=413)


def test_rejects_duplicate_photo(client: TestClient, complaint: dict) -> None:
    photo = make_image()
    assert upload_photo(client, complaint["id"], photo).status_code == 201
    response = upload_photo(client, complaint["id"], photo)
    assert response.status_code == 409


def test_photo_limit(client: TestClient, complaint: dict) -> None:
    for i in range(5):
        assert (
            upload_photo(client, complaint["id"], make_image("PNG", (100 + i, 100))).status_code
            == 201
        )
    response = upload_photo(client, complaint["id"], make_image("PNG", (200, 100)))
    assert response.status_code == 422


def test_upload_requires_login(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/complaints/{uuid.uuid4()}/evidence",
        files={"file": ("p.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 401


def test_cannot_upload_after_submission(client: TestClient, complaint: dict, db: Session) -> None:
    row = db.get(Complaint, uuid.UUID(complaint["id"]))
    assert row is not None
    row.status = "SUBMITTED"
    db.commit()
    assert upload_photo(client, complaint["id"]).status_code == 409


# ── Serving the file ────────────────────────────────────────────────────────


def test_owner_can_view_photo(client: TestClient, complaint: dict) -> None:
    evidence = upload_photo(client, complaint["id"]).json()
    response = client.get(evidence["url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "private, max-age=3600"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert Image.open(io.BytesIO(response.content)).format == "JPEG"


def test_photo_requires_login(client: TestClient, complaint: dict) -> None:
    evidence = upload_photo(client, complaint["id"]).json()
    client.cookies.clear()
    assert client.get(evidence["url"]).status_code == 401


# ── Ownership: another user can't see, add to, or delete my photos ─────────


def test_other_user_cannot_access_my_evidence(
    client: TestClient, other_client: TestClient, complaint: dict
) -> None:
    evidence = upload_photo(client, complaint["id"]).json()

    assert other_client.get(evidence["url"]).status_code == 404
    assert (
        other_client.delete(
            f"/api/v1/evidence/{evidence['id']}", headers=csrf_headers(other_client)
        ).status_code
        == 404
    )
    assert upload_photo(other_client, complaint["id"]).status_code == 404

    # Still intact for the owner.
    assert client.get(evidence["url"]).status_code == 200
    assert len(client.get(f"/api/v1/complaints/{complaint['id']}").json()["evidence"]) == 1


# ── Removing a photo ────────────────────────────────────────────────────────


def test_delete_photo_from_draft(
    client: TestClient, complaint: dict, storage: LocalStorage, db: Session
) -> None:
    evidence_id = upload_photo(client, complaint["id"]).json()["id"]
    key = db.get(Evidence, uuid.UUID(evidence_id)).file_storage_key  # type: ignore[union-attr]

    response = client.delete(f"/api/v1/evidence/{evidence_id}", headers=csrf_headers(client))
    assert response.status_code == 204
    assert client.get(f"/api/v1/evidence/{evidence_id}/file").status_code == 404
    with pytest.raises(FileNotFoundError):
        storage.read(key)
    timeline = client.get(f"/api/v1/complaints/{complaint['id']}/timeline").json()
    assert timeline[-1]["event_type"] == "EVIDENCE_REMOVED"


def test_cannot_delete_photo_after_submission(
    client: TestClient, complaint: dict, db: Session
) -> None:
    evidence_id = upload_photo(client, complaint["id"]).json()["id"]
    row = db.get(Complaint, uuid.UUID(complaint["id"]))
    assert row is not None
    row.status = "SUBMITTED"
    db.commit()
    response = client.delete(f"/api/v1/evidence/{evidence_id}", headers=csrf_headers(client))
    assert response.status_code == 409


# ── Storage safety ──────────────────────────────────────────────────────────


def test_local_storage_rejects_path_traversal(storage: LocalStorage) -> None:
    with pytest.raises(ValueError):
        storage.save("../../outside.txt", b"x")

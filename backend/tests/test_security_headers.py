"""Every API response carries the security headers; private photos keep their own caching."""

from fastapi.testclient import TestClient

from tests.conftest import create_complaint, register, upload_photo


def test_api_responses_are_hardened_and_not_cached(client: TestClient) -> None:
    for response in (client.get("/api/v1/health"), client.get("/api/v1/auth/me")):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in response.headers["content-security-policy"]


def test_photos_keep_their_private_cache_rule(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    photo = upload_photo(client, complaint["id"]).json()
    response = client.get(photo["url"])
    assert response.headers["cache-control"] == "private, max-age=3600"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_a_refused_upload_still_gets_the_headers(client: TestClient) -> None:
    register(client)
    complaint = create_complaint(client)
    response = client.post(
        f"/api/v1/complaints/{complaint['id']}/evidence",
        content=b"x",
        headers={"Content-Length": str(50 * 1024 * 1024), "Content-Type": "image/jpeg"},
    )
    assert response.status_code == 413
    assert response.headers["x-frame-options"] == "DENY"

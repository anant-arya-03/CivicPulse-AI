from fastapi.testclient import TestClient

from tests.conftest import csrf_headers, register


def test_health_reports_database_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_timestamps_are_returned_in_utc(client: TestClient) -> None:
    register(client)
    created_at = client.get("/api/v1/auth/me").json()["user"]["created_at"]
    assert created_at.endswith(("Z", "+00:00")), created_at


def test_update_profile_name(client: TestClient) -> None:
    register(client)
    response = client.patch(
        "/api/v1/users/me", json={"name": "  Asha  K Rao "}, headers=csrf_headers(client)
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Asha K Rao"
    assert client.get("/api/v1/auth/me").json()["user"]["name"] == "Asha K Rao"


def test_update_profile_validates_name(client: TestClient) -> None:
    register(client)
    response = client.patch("/api/v1/users/me", json={"name": "A"}, headers=csrf_headers(client))
    assert response.status_code == 422


def test_update_profile_requires_login(client: TestClient) -> None:
    response = client.patch("/api/v1/users/me", json={"name": "Someone"})
    assert response.status_code == 401


def test_unknown_route_uses_standard_error_shape(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

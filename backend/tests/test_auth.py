from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.auth.models import UserSession
from app.modules.users.models import User
from tests.conftest import csrf_headers, register

SESSION_COOKIE = get_settings().session_cookie_name
CSRF_COOKIE = get_settings().csrf_cookie_name


# ── Registration ────────────────────────────────────────────────────────────


def test_register_creates_user_and_logs_in(client: TestClient, db: Session) -> None:
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "asha@example.com"
    assert body["user"]["name"] == "Asha Rao"
    assert "password" not in str(body).lower()

    assert client.cookies.get(SESSION_COOKIE)
    assert client.cookies.get(CSRF_COOKIE)
    assert client.get("/api/v1/auth/me").status_code == 200


def test_password_is_hashed_never_stored_plain(client: TestClient, db: Session) -> None:
    register(client, password="Secret123")
    user = db.scalar(select(User).where(User.email == "asha@example.com"))
    assert user is not None
    assert user.password_hash != "Secret123"
    assert user.password_hash.startswith("$argon2")


def test_session_token_is_stored_only_as_hash(client: TestClient, db: Session) -> None:
    register(client)
    raw_token = client.cookies.get(SESSION_COOKIE)
    stored = db.scalars(select(UserSession.token_hash)).all()
    assert len(stored) == 1
    assert stored[0] != raw_token
    assert len(stored[0]) == 64


def test_register_normalizes_email_and_name(client: TestClient) -> None:
    response = register(client, email="  Asha@Example.COM ", name="  Asha   Rao ")
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "asha@example.com"
    assert response.json()["user"]["name"] == "Asha Rao"


def test_register_duplicate_email_is_rejected(client: TestClient) -> None:
    register(client)
    client.cookies.clear()
    response = register(client, email="ASHA@example.com")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_register_rejects_weak_password(client: TestClient) -> None:
    for weak in ["short1", "lettersonly", "12345678"]:
        response = register(client, password=weak)
        assert response.status_code == 422, weak
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_rejects_invalid_email(client: TestClient) -> None:
    response = register(client, email="not-an-email")
    assert response.status_code == 422
    fields = [f["field"] for f in response.json()["error"]["details"]["fields"]]
    assert "email" in fields


# ── Login ───────────────────────────────────────────────────────────────────


def test_login_with_correct_credentials(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/login", json={"email": "Asha@Example.com", "password": "Secret123"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "asha@example.com"
    assert client.get("/api/v1/auth/me").status_code == 200


def test_login_with_wrong_password_fails(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/login", json={"email": "asha@example.com", "password": "Wrong123"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Incorrect email or password."
    assert not client.cookies.get(SESSION_COOKIE)


def test_login_unknown_email_gives_same_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Secret123"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Incorrect email or password."


def test_login_inactive_user_fails(client: TestClient, db: Session) -> None:
    register(client)
    client.cookies.clear()
    user = db.scalar(select(User))
    assert user is not None
    user.is_active = False
    db.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "asha@example.com", "password": "Secret123"}
    )
    assert response.status_code == 401


def test_login_is_rate_limited(client: TestClient) -> None:
    payload = {"email": "nobody@example.com", "password": "Secret123"}
    codes = [client.post("/api/v1/auth/login", json=payload).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


# ── Session, logout, protected routes ──────────────────────────────────────


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_forged_session_cookie_is_rejected(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, "made-up-token")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_revokes_session(client: TestClient) -> None:
    register(client)
    old_token = client.cookies.get(SESSION_COOKIE)
    assert old_token

    response = client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    assert response.status_code == 204

    # Even if someone kept a copy of the old cookie, it no longer works.
    client.cookies.set(SESSION_COOKIE, old_token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_session_is_rejected(client: TestClient, db: Session) -> None:
    from datetime import timedelta

    from app.common.time import utc_now

    register(client)
    session = db.scalar(select(UserSession))
    assert session is not None
    session.expires_at = utc_now() - timedelta(minutes=1)
    db.commit()

    assert client.get("/api/v1/auth/me").status_code == 401


# ── CSRF ───────────────────────────────────────────────────────────────────


def test_state_changing_request_without_csrf_token_is_rejected(client: TestClient) -> None:
    register(client)
    response = client.patch("/api/v1/users/me", json={"name": "New Name"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


def test_state_changing_request_with_wrong_csrf_token_is_rejected(client: TestClient) -> None:
    register(client)
    response = client.patch(
        "/api/v1/users/me", json={"name": "New Name"}, headers={"X-CSRF-Token": "guess"}
    )
    assert response.status_code == 403


def test_logout_requires_csrf_token(client: TestClient) -> None:
    register(client)
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.get("/api/v1/auth/me").status_code == 200  # still logged in

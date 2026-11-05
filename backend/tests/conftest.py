"""Shared pytest fixtures.

How test isolation works:
1. Once per test run, the TEST database is migrated to the latest schema with Alembic.
2. Each test runs inside a database transaction that is rolled back afterwards,
   so tests never see each other's data and the test database stays empty.
"""

import io
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR, get_settings
from app.core.database import get_db
from app.core.rate_limit import reset_rate_limits
from app.integrations.ai_providers.factory import get_ai_provider
from app.integrations.ai_providers.mock_provider import MockAIProvider
from app.integrations.email_providers.factory import get_email_provider
from app.integrations.email_providers.mock_provider import MockEmailProvider
from app.integrations.geocoding.factory import get_geocoder
from app.integrations.geocoding.mock_geocoder import MockGeocoder
from app.integrations.storage.factory import get_storage
from app.integrations.storage.local_storage import LocalStorage
from app.modules.authorities.service import seed_demo_authorities

os.environ["APP_ENV"] = "test"
get_settings.cache_clear()

from app.main import app  # noqa: E402  (import after the test env is set)


def _test_database_url() -> str:
    settings = get_settings()
    url = settings.test_database_url
    if not url:
        pytest.exit("TEST_DATABASE_URL is not set in .env", returncode=1)
    if url == settings.database_url or "test" not in url:
        # Safety net: tests delete data, so never let them touch the development database.
        pytest.exit("TEST_DATABASE_URL must be a separate database with 'test' in its name.", 1)
    return url


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = _test_database_url()
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", url)
    alembic_config.attributes["configure_logger"] = False
    command.upgrade(alembic_config, "head")

    test_engine = create_engine(url)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def db(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    # "create_savepoint" turns the app's db.commit() calls into savepoints, so the
    # outer transaction can still roll everything back at the end of the test.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def storage(tmp_path: Path) -> LocalStorage:
    """Each test gets its own empty folder for uploaded files."""
    return LocalStorage(tmp_path / "storage")


@pytest.fixture()
def ai(client: TestClient) -> MockAIProvider:
    """The AI provider used by the app in this test. Change `ai.scenario` to simulate outcomes."""
    return app.dependency_overrides[get_ai_provider]()  # type: ignore[no-any-return]


@pytest.fixture()
def email(client: TestClient) -> MockEmailProvider:
    """The simulated email provider for this test. Set `email.scenario`; inspect `email.sent`."""
    return app.dependency_overrides[get_email_provider]()  # type: ignore[no-any-return]


@pytest.fixture()
def demo_directory(db: Session) -> None:
    """Load the fictional Demo City departments into the test database."""
    seed_demo_authorities(db)


@pytest.fixture()
def client(db: Session, storage: LocalStorage) -> Iterator[TestClient]:
    mock_ai = MockAIProvider("pothole")
    mock_email = MockEmailProvider("success")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_geocoder] = MockGeocoder
    app.dependency_overrides[get_ai_provider] = lambda: mock_ai
    app.dependency_overrides[get_email_provider] = lambda: mock_email
    reset_rate_limits()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def other_client(client: TestClient) -> Iterator[TestClient]:
    """A second browser, logged in as a different user (for ownership tests)."""
    with TestClient(app) as second:
        register(second, name="Other Person", email="other@example.com")
        yield second


# ── Helpers ─────────────────────────────────────────────────────────────────


def make_image(
    image_format: str = "JPEG", size: tuple[int, int] = (320, 240), *, with_gps_exif: bool = False
) -> bytes:
    """Create a real image in memory. Optionally embed EXIF with a GPS location."""
    image = Image.new("RGB", size, color=(120, 90, 60))
    buffer = io.BytesIO()
    if with_gps_exif:
        exif = Image.Exif()
        exif[0x010F] = "TestPhoneMaker"  # Make
        gps = exif.get_ifd(0x8825)
        gps[1], gps[2] = "N", (12.0, 58.0, 17.0)  # latitude
        gps[3], gps[4] = "E", (77.0, 35.0, 40.0)  # longitude
        image.save(buffer, format=image_format, exif=exif)
    else:
        image.save(buffer, format=image_format)
    return buffer.getvalue()


def create_complaint(client: TestClient, **fields: object) -> dict:
    response = client.post("/api/v1/complaints", json=fields, headers=csrf_headers(client))
    assert response.status_code == 201, response.text
    return response.json()


def upload_photo(
    client: TestClient,
    complaint_id: str,
    data: bytes | None = None,
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
):
    return client.post(
        f"/api/v1/complaints/{complaint_id}/evidence",
        files={"file": (filename, data if data is not None else make_image(), content_type)},
        headers=csrf_headers(client),
    )


def register(client: TestClient, **overrides: str):
    payload = {"name": "Asha Rao", "email": "asha@example.com", "password": "Secret123"}
    payload.update(overrides)
    return client.post("/api/v1/auth/register", json=payload)


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get(get_settings().csrf_cookie_name) or ""}

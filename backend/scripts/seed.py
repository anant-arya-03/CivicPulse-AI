"""Seed development data.

Run from the backend/ folder:  python -m scripts.seed

Safe to run repeatedly: existing records are left alone.
"""

import app.models  # noqa: F401  (registers every ORM model)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.authorities import service as authority_service
from app.modules.users import service as user_service

DEMO_USER_EMAIL = "demo@civicpulse.example"
DEMO_USER_PASSWORD = "DemoPass123"  # development only, never used in production
DEMO_USER_NAME = "Demo Citizen"


def seed() -> None:
    if get_settings().is_production:
        raise SystemExit("Refusing to seed demo data in production.")

    with SessionLocal() as db:
        if user_service.get_user_by_email(db, DEMO_USER_EMAIL):
            print(f"Demo user already exists: {DEMO_USER_EMAIL}")
        else:
            user_service.create_user(
                db,
                name=DEMO_USER_NAME,
                email=DEMO_USER_EMAIL,
                password_hash=hash_password(DEMO_USER_PASSWORD),
            )
            db.commit()
            print(f"Created demo user: {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}")

        count = authority_service.seed_demo_authorities(db)
        print(f"Demo authority directory ready: {count} FICTIONAL departments in Demo City (XX)")


if __name__ == "__main__":
    seed()

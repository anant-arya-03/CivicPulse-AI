import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.users.schemas import UserUpdate


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def create_user(db: Session, *, name: str, email: str, password_hash: str) -> User:
    """Add a user to the session. The caller commits, so it can combine this with other writes."""
    user = User(name=name, email=normalize_email(email), password_hash=password_hash)
    db.add(user)
    db.flush()  # assigns defaults and surfaces unique-constraint errors early
    return user


def update_profile(db: Session, user: User, data: UserUpdate) -> User:
    user.name = data.name
    db.commit()
    return user

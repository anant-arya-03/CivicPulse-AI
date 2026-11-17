import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.users.schemas import PasswordChange, SettingsUpdate, UserUpdate


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


def update_settings(db: Session, user: User, data: SettingsUpdate) -> User:
    user.notification_preferences = data.notification_preferences.model_dump()
    user.privacy_settings = data.privacy_settings.model_dump()
    db.commit()
    return user


def change_password(db: Session, user: User, data: PasswordChange) -> None:
    # Local imports avoid the auth service's dependency on this module.
    from app.common.time import utc_now
    from app.core.errors import BusinessRuleError
    from app.core.security import hash_password, verify_password
    from app.modules.auth.models import UserSession

    if not verify_password(data.current_password, user.password_hash):
        raise BusinessRuleError("The current password is incorrect.")
    user.password_hash = hash_password(data.new_password)
    for session in db.scalars(select(UserSession).where(UserSession.user_id == user.id)):
        session.revoked_at = utc_now()
    db.commit()

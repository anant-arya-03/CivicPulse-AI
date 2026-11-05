"""Authentication business logic: registration, credential checks, and session lifecycle."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthenticatedError
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.modules.auth.models import UserSession
from app.modules.auth.schemas import RegisterRequest
from app.modules.users import service as user_service
from app.modules.users.models import User

# Avoid a database write on every request: only refresh `last_used_at` this often.
_LAST_USED_UPDATE_INTERVAL = timedelta(minutes=5)


def register_user(db: Session, data: RegisterRequest) -> User:
    if user_service.get_user_by_email(db, data.email) is not None:
        raise ConflictError("An account with this email already exists.")
    try:
        user = user_service.create_user(
            db, name=data.name, email=data.email, password_hash=hash_password(data.password)
        )
        db.commit()
    except IntegrityError as exc:  # two sign-ups with the same email at the same moment
        db.rollback()
        raise ConflictError("An account with this email already exists.") from exc
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = user_service.get_user_by_email(db, email)
    password_ok = verify_password(password, user.password_hash if user else None)
    if user is None or not password_ok or not user.is_active:
        # Same message for every case, so attackers can't tell which part was wrong.
        raise UnauthenticatedError("Incorrect email or password.")
    return user


def start_session(db: Session, user: User, user_agent: str | None) -> str:
    """Create a session row and return the raw token (to be placed in the cookie)."""
    now = utc_now()
    token = generate_session_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=now + timedelta(hours=get_settings().session_ttl_hours),
            last_used_at=now,
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    user.last_login_at = now
    db.commit()
    return token


def get_user_for_session_token(db: Session, token: str) -> User | None:
    """Return the user for a valid, unexpired, unrevoked session, or None."""
    now = utc_now()
    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_session_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )
    if session is None or not session.user.is_active:
        return None

    if session.last_used_at is None or now - session.last_used_at > _LAST_USED_UPDATE_INTERVAL:
        session.last_used_at = now
        db.commit()
    return session.user


def end_session(db: Session, token: str) -> None:
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_session_token(token))
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = utc_now()
        db.commit()

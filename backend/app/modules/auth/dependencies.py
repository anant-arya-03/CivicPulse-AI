"""FastAPI dependencies for authentication and CSRF protection."""

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import get_settings
from app.core.database import DbSession
from app.core.errors import CSRFError, UnauthenticatedError
from app.core.security import is_valid_csrf_token
from app.modules.auth import service
from app.modules.users.models import User

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# These endpoints create a new session, so there is no existing session to protect yet.
CSRF_EXEMPT_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register"}


def get_current_user(request: Request, db: DbSession) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    user = service.get_user_for_session_token(db, token) if token else None
    if user is None:
        raise UnauthenticatedError("Please log in to continue.")
    return user


# Use in route signatures: `def handler(user: CurrentUser): ...`
CurrentUser = Annotated[User, Depends(get_current_user)]


def verify_csrf(request: Request) -> None:
    """Applied to every route (see main.py). Only state-changing requests that carry a
    session cookie are checked; everything else passes straight through."""
    if request.method in SAFE_METHODS or request.url.path in CSRF_EXEMPT_PATHS:
        return
    settings = get_settings()
    session_token = request.cookies.get(settings.session_cookie_name)
    if session_token is None:
        return  # not logged in: the route itself will reject the request if it needs auth
    if not is_valid_csrf_token(session_token, request.headers.get("X-CSRF-Token")):
        raise CSRFError("Security check failed. Please refresh the page and try again.")

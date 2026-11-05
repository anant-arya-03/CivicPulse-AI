"""Helpers for setting and clearing the session + CSRF cookies on a response."""

from fastapi import Response

from app.core.config import get_settings
from app.core.security import csrf_token_for


def set_auth_cookies(response: Response, session_token: str) -> None:
    settings = get_settings()
    max_age = settings.session_ttl_hours * 3600

    # HttpOnly: JavaScript can never read the session token.
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    # Readable by our frontend so it can echo it in the X-CSRF-Token header.
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token_for(session_token),
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (settings.session_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="lax")

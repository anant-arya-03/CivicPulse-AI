"""Security primitives: password hashing, session tokens, and CSRF tokens.

How sessions work:
1. On login we generate a random token and send it to the browser in an HttpOnly cookie.
2. The database stores only the SHA-256 hash of that token, so a leaked database
   cannot be used to log in as anyone.
3. The CSRF token is an HMAC of the session token (keyed by SECRET_KEY). The browser
   can read it (non-HttpOnly cookie) and must echo it in the `X-CSRF-Token` header on
   every state-changing request. A malicious site cannot read our cookies, so it
   cannot forge that header.
"""

import hashlib
import hmac
import secrets

from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hash = PasswordHash.recommended()  # Argon2id with safe defaults

# Used to keep login timing similar whether or not the email exists.
_DUMMY_PASSWORD_HASH = _password_hash.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check a password. With no stored hash, still spend the same time hashing."""
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_PASSWORD_HASH)
        return False
    return _password_hash.verify(password, password_hash)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_token_for(session_token: str) -> str:
    secret = get_settings().secret_key.encode("utf-8")
    return hmac.new(secret, session_token.encode("utf-8"), hashlib.sha256).hexdigest()


def is_valid_csrf_token(session_token: str, provided: str | None) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(csrf_token_for(session_token), provided)

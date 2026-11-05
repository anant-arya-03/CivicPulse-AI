"""Time helpers.

Always use `utc_now()` instead of `datetime.now()`, so time can be controlled in tests and demos.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)

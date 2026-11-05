"""The fingerprint of an outgoing message. Approval stores it; sending checks it again, so only
the exact content the citizen approved can ever be sent."""

import hashlib
import json
from collections.abc import Iterable

from app.modules.communications.models import Communication


def content_sha256(
    *, to: str | None, subject: str, body: str, attachment_ids: Iterable[str]
) -> str:
    payload = {"to": to, "subject": subject, "body": body, "attachments": sorted(attachment_ids)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def message_sha256(message: Communication) -> str:
    """Hash of a stored message (the same formula as for a complaint's preview)."""
    return content_sha256(
        to=message.recipient,
        subject=message.subject,
        body=message.body,
        attachment_ids=(a["evidence_id"] for a in message.attachments),
    )

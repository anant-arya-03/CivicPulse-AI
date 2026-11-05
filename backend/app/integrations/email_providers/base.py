"""The email provider interface used to submit complaints.

Only a simulated provider exists in this project. A real one (e.g. Gmail API with OAuth) would
implement the same interface, set `is_simulated = False`, and is additionally gated by the
safety checks in communications/service.py.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    body: str
    from_address: str
    # Sent to the provider so that a retried send can never produce a second email.
    idempotency_key: str
    attachment_names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str


class EmailProviderError(Exception):
    """The email could not be sent (the provider was unreachable, refused it, etc.)."""


class EmailProvider(Protocol):
    name: str
    # True means nothing ever leaves this computer. The UI and records say "simulated".
    is_simulated: bool

    def send(self, email: OutgoingEmail) -> SendResult: ...

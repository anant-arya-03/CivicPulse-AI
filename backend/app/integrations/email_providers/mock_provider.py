"""A simulated email provider. It sends NOTHING; it only records what would have been sent.

Scenarios (MOCK_EMAIL_SCENARIO):
  success   every send is accepted
  failure   every send fails (to see the error screen and retry button)
  flaky     the first attempt for each message fails, the retry succeeds

Like real providers, it is idempotent: sending the same idempotency key twice returns the same
message id and does not count as a second email.
"""

import hashlib
import threading

from app.integrations.email_providers.base import EmailProviderError, OutgoingEmail, SendResult


class MockEmailProvider:
    name = "mock"
    is_simulated = True

    def __init__(self, scenario: str = "success") -> None:
        self.scenario = scenario
        self._lock = threading.Lock()
        self.sent: dict[str, OutgoingEmail] = {}  # idempotency key -> the "sent" email
        self._attempts: dict[str, int] = {}

    def send(self, email: OutgoingEmail) -> SendResult:
        with self._lock:
            message_id = "mock-" + hashlib.sha256(email.idempotency_key.encode()).hexdigest()[:16]
            if email.idempotency_key in self.sent:
                return SendResult(provider_message_id=message_id)  # duplicate: no second email

            attempt = self._attempts.get(email.idempotency_key, 0) + 1
            self._attempts[email.idempotency_key] = attempt
            if self.scenario == "failure" or (self.scenario == "flaky" and attempt == 1):
                raise EmailProviderError("The simulated mail server is unavailable.")

            self.sent[email.idempotency_key] = email
            return SendResult(provider_message_id=message_id)

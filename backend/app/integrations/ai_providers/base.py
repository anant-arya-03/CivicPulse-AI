"""The AI provider interface. Agents (app/modules/ai/agents/) only talk to this, so switching
between the mock and a real model, or adding another vendor, never changes agent code."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class ImagePart:
    data: bytes
    media_type: str  # "image/jpeg", "image/png", or "image/webp"


ContentPart = TextPart | ImagePart


@dataclass(frozen=True)
class AIResult(Generic[T]):  # noqa: UP046  (PEP 695 syntax needs Python 3.12+)
    output: T  # already validated against the requested Pydantic schema
    provider: str
    model: str
    is_mock: bool
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class AIProviderError(Exception):
    """The provider couldn't be used: network error, timeout, rate limit, outage, refusal."""

    def __init__(self, message: str, *, code: str = "PROVIDER_ERROR") -> None:
        super().__init__(message)
        self.code = code


class AIOutputError(AIProviderError):
    """The provider answered, but the answer didn't match the required schema."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="INVALID_OUTPUT")


class AIProvider(Protocol):
    name: str
    model: str
    is_mock: bool

    def generate_structured(
        self,
        *,
        task: str,  # e.g. "vision.v1" (lets the mock pick the right sample answer)
        system_prompt: str,
        content: Sequence[ContentPart],
        output_schema: type[T],
        max_tokens: int,
    ) -> AIResult[T]: ...

"""Claude (Anthropic) adapter using the official `anthropic` SDK.

- Structured outputs: `messages.parse(output_format=PydanticModel)` makes Claude reply in that
  JSON shape, and the SDK validates the reply with Pydantic.
- Refusals: if Claude's safety checks decline, `stop_reason` is "refusal". The server-side
  `fallbacks="default"` option first retries on Anthropic's recommended fallback model; if the
  answer is still a refusal, we raise an error and the UI offers the manual path.
- The API key is read from the server's environment only. It is never sent to the browser.
"""

import base64
import time
from collections.abc import Sequence
from typing import Any

import anthropic
from pydantic import ValidationError

from app.integrations.ai_providers.base import (
    AIOutputError,
    AIProviderError,
    AIResult,
    ContentPart,
    ImagePart,
    T,
)

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"
    is_mock = False

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        effort: str = "medium",
        timeout_seconds: float = 90,
        client: Any | None = None,  # tests pass a fake client; real code builds one
    ) -> None:
        self.model = model
        self.effort = effort
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=timeout_seconds, max_retries=2
        )

    def generate_structured(
        self,
        *,
        task: str,
        system_prompt: str,
        content: Sequence[ContentPart],
        output_schema: type[T],
        max_tokens: int,
    ) -> AIResult[T]:
        started = time.monotonic()
        try:
            response = self._client.beta.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": [_to_block(part) for part in content]}],
                output_format=output_schema,
                output_config={"effort": self.effort},
                betas=[_FALLBACK_BETA],
                fallbacks="default",
            )
        except ValidationError as exc:
            raise AIOutputError("The model's answer did not match the expected format.") from exc
        except anthropic.RateLimitError as exc:
            raise AIProviderError("The AI service is busy.", code="RATE_LIMITED") from exc
        except anthropic.APITimeoutError as exc:
            raise AIProviderError(
                "The AI service took too long to answer.", code="TIMEOUT"
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderError("Could not reach the AI service.") from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderError(f"The AI service returned an error ({exc.status_code}).") from exc

        if response.stop_reason == "refusal":
            raise AIProviderError("The AI declined to analyse this request.", code="REFUSED")
        if response.stop_reason == "max_tokens":
            raise AIOutputError("The model's answer was cut off before it was complete.")
        parsed = response.parsed_output
        if parsed is None:
            raise AIOutputError("The model did not return a structured answer.")

        usage = getattr(response, "usage", None)
        return AIResult(
            output=parsed,
            provider=self.name,
            model=getattr(response, "model", None) or self.model,
            is_mock=False,
            latency_ms=int((time.monotonic() - started) * 1000),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )


def _to_block(part: ContentPart) -> dict[str, Any]:
    if isinstance(part, ImagePart):
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": part.media_type,
                "data": base64.b64encode(part.data).decode("ascii"),
            },
        }
    return {"type": "text", "text": part.text}

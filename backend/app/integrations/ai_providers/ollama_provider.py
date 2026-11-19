"""Structured inference through a local Ollama server."""

import base64
import json
import time
from collections.abc import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from pydantic import ValidationError

from app.integrations.ai_providers.base import (
    AIOutputError,
    AIProviderError,
    AIResult,
    ContentPart,
    ImagePart,
    T,
    TextPart,
)


class OllamaProvider:
    name = "ollama"
    is_mock = False

    def __init__(self, *, model: str, timeout_seconds: float) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._http = build_opener(ProxyHandler({}))

    def generate_structured(
        self,
        *,
        task: str,
        system_prompt: str,
        content: Sequence[ContentPart],
        output_schema: type[T],
        max_tokens: int,
    ) -> AIResult[T]:
        text = "\n".join(part.text for part in content if isinstance(part, TextPart))
        images = [
            base64.b64encode(part.data).decode("ascii")
            for part in content
            if isinstance(part, ImagePart)
        ]
        if images:
            text += "\nThe attached images are in the order described above."
        request = Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(
                {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text, "images": images},
                    ],
                    "format": output_schema.model_json_schema(),
                    "stream": False,
                    "options": {"temperature": 0, "num_predict": max_tokens},
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.monotonic()
        try:
            with self._http.open(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as exc:
            raise AIProviderError(f"Ollama returned an error ({exc.code}).") from exc
        except TimeoutError as exc:
            raise AIProviderError(
                "The local model took too long to answer.", code="TIMEOUT"
            ) from exc
        except (URLError, OSError) as exc:
            raise AIProviderError("Could not reach the local Ollama server.") from exc
        except ValueError as exc:
            raise AIOutputError("Ollama did not return a JSON response.") from exc

        try:
            if payload.get("done_reason") == "length":
                raise AIOutputError("The local model's answer was cut off.")
            output = output_schema.model_validate_json(payload["message"]["content"])
        except (AttributeError, KeyError, TypeError, ValidationError) as exc:
            raise AIOutputError(
                "The local model's answer did not match the expected format."
            ) from exc

        return AIResult(
            output=output,
            provider=self.name,
            model=self.model,
            is_mock=False,
            latency_ms=int((time.monotonic() - started) * 1000),
            input_tokens=payload.get("prompt_eval_count"),
            output_tokens=payload.get("eval_count"),
        )

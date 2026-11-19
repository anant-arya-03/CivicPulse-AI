import io
import json
from unittest.mock import Mock
from urllib.error import URLError

import pytest
from pydantic import BaseModel

from app.integrations.ai_providers.base import AIOutputError, AIProviderError, ImagePart, TextPart
from app.integrations.ai_providers.ollama_provider import OllamaProvider


class Comparison(BaseModel):
    same_place: bool


def _compare(provider: OllamaProvider):
    return provider.generate_structured(
        task="resolution.v1",
        system_prompt="Compare the photos.",
        content=[
            TextPart("Before"),
            ImagePart(b"first", "image/jpeg"),
            TextPart("After"),
            ImagePart(b"second", "image/jpeg"),
        ],
        output_schema=Comparison,
        max_tokens=100,
    )


def test_preserves_image_order_and_validates_output(monkeypatch):
    provider = OllamaProvider(model="gemma3:4b", timeout_seconds=15)
    response = {
        "message": {"content": '{"same_place": true}'},
        "done_reason": "stop",
        "eval_count": 12,
    }
    open_request = Mock(return_value=io.BytesIO(json.dumps(response).encode()))
    monkeypatch.setattr(provider._http, "open", open_request)

    result = _compare(provider)

    request = open_request.call_args.args[0]
    body = json.loads(request.data)
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert open_request.call_args.kwargs["timeout"] == 15
    assert body["format"] == Comparison.model_json_schema()
    assert body["messages"][1]["images"] == ["Zmlyc3Q=", "c2Vjb25k"]
    assert body["messages"][1]["content"].startswith("Before\nAfter")
    assert result.output.same_place is True
    assert result.is_mock is False
    assert result.output_tokens == 12


def test_schema_mismatch_becomes_provider_output_error(monkeypatch):
    provider = OllamaProvider(model="gemma3:4b", timeout_seconds=15)
    response = Mock(return_value=io.BytesIO(b'{"message":{"content":"{}"}}'))
    monkeypatch.setattr(provider._http, "open", response)
    with pytest.raises(AIOutputError):
        _compare(provider)


def test_unavailable_ollama_becomes_provider_error(monkeypatch):
    provider = OllamaProvider(model="gemma3:4b", timeout_seconds=15)
    monkeypatch.setattr(provider._http, "open", Mock(side_effect=URLError("offline")))
    with pytest.raises(AIProviderError, match="Could not reach"):
        _compare(provider)

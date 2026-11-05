"""The mock provider's scenarios, and the Claude adapter tested against a fake SDK client.

No test here calls the real Anthropic API (no network, no cost, no key needed)."""

import base64
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from app.integrations.ai_providers.anthropic_provider import AnthropicProvider
from app.integrations.ai_providers.base import AIOutputError, AIProviderError, ImagePart, TextPart
from app.integrations.ai_providers.mock_provider import VISION_SAMPLES, MockAIProvider
from app.modules.ai.schemas import ComplaintLetterProse, VisionAnalysis

IMAGE = ImagePart(data=b"\xff\xd8fake-jpeg", media_type="image/jpeg")


def call(provider: Any, schema: type = VisionAnalysis, task: str = "vision.v1"):
    return provider.generate_structured(
        task=task,
        system_prompt="system rules",
        content=[IMAGE, TextPart("analyse")],
        output_schema=schema,
        max_tokens=1000,
    )


# ── Mock provider ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("scenario", ["pothole", "streetlight", "garbage", "not_civic"])
def test_mock_scenarios_return_valid_output(scenario: str) -> None:
    result = call(MockAIProvider(scenario))
    assert isinstance(result.output, VisionAnalysis)
    assert result.is_mock is True
    assert result.provider == "mock"


def test_mock_not_civic_is_conservative() -> None:
    output = call(MockAIProvider("not_civic")).output
    assert output.is_civic_issue is False
    assert output.severity == "UNKNOWN"


def test_mock_failure_scenario() -> None:
    with pytest.raises(AIProviderError):
        call(MockAIProvider("failure"))


def test_mock_invalid_scenario_fails_validation() -> None:
    with pytest.raises(AIOutputError):
        call(MockAIProvider("invalid"))


def test_mock_letter_uses_the_facts() -> None:
    facts = (
        '<facts>\n{"title": "Pothole on Lake Road", "category_label": "Road pothole", '
        '"location_summary": "45 Lake Road", "citizen_description": "Deep hole."}\n</facts>'
    )
    result = MockAIProvider().generate_structured(
        task="complaint_letter.v1",
        system_prompt="",
        content=[TextPart(facts)],
        output_schema=ComplaintLetterProse,
        max_tokens=1000,
    )
    assert "Pothole on Lake Road" in result.output.subject
    assert "45 Lake Road" in result.output.issue_summary


# ── Claude adapter with a fake client ───────────────────────────────────────


class FakeMessages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def fake_client(messages: FakeMessages) -> Any:
    return SimpleNamespace(beta=SimpleNamespace(messages=messages))


def response(stop_reason: str = "end_turn", parsed: Any = "default") -> Any:
    output = VisionAnalysis.model_validate(VISION_SAMPLES["pothole"])
    return SimpleNamespace(
        stop_reason=stop_reason,
        parsed_output=output if parsed == "default" else parsed,
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=1200, output_tokens=300),
    )


def provider_with(messages: FakeMessages) -> AnthropicProvider:
    return AnthropicProvider(
        api_key="unused", model="claude-opus-5-5", effort="medium", client=fake_client(messages)
    )


def test_anthropic_request_shape() -> None:
    messages = FakeMessages(response())
    result = call(provider_with(messages))

    request = messages.calls[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["system"] == "system rules"
    assert request["output_format"] is VisionAnalysis  # structured output via Pydantic
    assert request["output_config"] == {"effort": "medium"}
    assert request["fallbacks"] == "default"  # server-side fallback on refusal
    assert request["betas"] == ["server-side-fallback-2026-07-01"]

    image_block, text_block = request["messages"][0]["content"]
    assert image_block["type"] == "image"
    assert image_block["source"]["media_type"] == "image/jpeg"
    assert base64.b64decode(image_block["source"]["data"]) == IMAGE.data
    assert text_block == {"type": "text", "text": "analyse"}

    assert result.is_mock is False
    assert (result.input_tokens, result.output_tokens) == (1200, 300)
    assert result.output.category == "ROAD_POTHOLE"


@pytest.mark.parametrize(
    ("fake_response", "error_type", "code"),
    [
        (response(stop_reason="refusal"), AIProviderError, "REFUSED"),
        (response(stop_reason="max_tokens"), AIOutputError, "INVALID_OUTPUT"),
        (response(parsed=None), AIOutputError, "INVALID_OUTPUT"),
    ],
)
def test_anthropic_unusable_answers(fake_response: Any, error_type: type, code: str) -> None:
    with pytest.raises(error_type) as exc_info:
        call(provider_with(FakeMessages(fake_response)))
    assert exc_info.value.code == code


def test_anthropic_schema_violation_becomes_output_error() -> None:
    try:
        VisionAnalysis.model_validate({"category": "VOLCANO"})
    except ValidationError as exc:
        validation_error = exc
    with pytest.raises(AIOutputError):
        call(provider_with(FakeMessages(error=validation_error)))


def _request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (anthropic.APIConnectionError(request=_request()), "PROVIDER_ERROR"),
        (anthropic.APITimeoutError(request=_request()), "TIMEOUT"),
        (
            anthropic.RateLimitError(
                "slow down", response=httpx2.Response(429, request=_request()), body=None
            ),
            "RATE_LIMITED",
        ),
        (
            anthropic.InternalServerError(
                "oops", response=httpx2.Response(500, request=_request()), body=None
            ),
            "PROVIDER_ERROR",
        ),
    ],
)
def test_anthropic_sdk_errors_are_mapped(error: Exception, code: str) -> None:
    with pytest.raises(AIProviderError) as exc_info:
        call(provider_with(FakeMessages(error=error)))
    assert exc_info.value.code == code

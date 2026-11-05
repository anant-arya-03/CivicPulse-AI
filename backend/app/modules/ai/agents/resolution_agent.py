"""Resolution agent: before + after photos in, a structured comparison out (advice only)."""

from app.integrations.ai_providers.base import AIProvider, AIResult, ImagePart, TextPart
from app.modules.ai.prompts import resolution_v1 as prompt
from app.modules.ai.schemas import ResolutionAssessment

PROMPT_VERSION = prompt.PROMPT_VERSION
MAX_TOKENS = 16000


def compare_photos(
    provider: AIProvider, before: ImagePart, after: ImagePart
) -> AIResult[ResolutionAssessment]:
    return provider.generate_structured(
        task=PROMPT_VERSION,
        system_prompt=prompt.SYSTEM_PROMPT,
        content=[
            TextPart(prompt.BEFORE_LABEL),
            before,
            TextPart(prompt.AFTER_LABEL),
            after,
            TextPart(prompt.USER_TEXT),
        ],
        output_schema=ResolutionAssessment,
        max_tokens=MAX_TOKENS,
    )

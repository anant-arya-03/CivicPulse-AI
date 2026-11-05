"""Vision agent: one photo in, structured suggestions out (VisionAnalysis)."""

from app.integrations.ai_providers.base import AIProvider, AIResult, ImagePart, TextPart
from app.modules.ai.prompts import vision_v1 as prompt
from app.modules.ai.schemas import VisionAnalysis

PROMPT_VERSION = prompt.PROMPT_VERSION
MAX_TOKENS = 16000  # room for the model's reasoning plus the short structured answer


def analyze_photo(provider: AIProvider, image: ImagePart) -> AIResult[VisionAnalysis]:
    return provider.generate_structured(
        task=PROMPT_VERSION,
        system_prompt=prompt.SYSTEM_PROMPT,
        content=[image, TextPart(prompt.USER_TEXT)],
        output_schema=VisionAnalysis,
        max_tokens=MAX_TOKENS,
    )

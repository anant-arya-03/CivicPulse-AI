"""Complaint Letter agent: confirmed facts in, letter wording out (ComplaintLetterProse)."""

from typing import Any

from app.integrations.ai_providers.base import AIProvider, AIResult, TextPart
from app.modules.ai.letter_template import facts_as_prompt_text
from app.modules.ai.prompts import complaint_letter_v1 as prompt
from app.modules.ai.schemas import ComplaintLetterProse

PROMPT_VERSION = prompt.PROMPT_VERSION
MAX_TOKENS = 16000


def write_letter_prose(
    provider: AIProvider, facts: dict[str, Any]
) -> AIResult[ComplaintLetterProse]:
    return provider.generate_structured(
        task=PROMPT_VERSION,
        system_prompt=prompt.SYSTEM_PROMPT,
        content=[TextPart(facts_as_prompt_text(facts))],
        output_schema=ComplaintLetterProse,
        max_tokens=MAX_TOKENS,
    )

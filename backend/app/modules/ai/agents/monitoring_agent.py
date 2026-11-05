"""Monitoring agent: reads department replies (ReplyClassification) and writes the wording of
follow-up reminders (FollowupProse). It never decides what happens; monitoring/rules.py does."""

from typing import Any

from app.integrations.ai_providers.base import AIProvider, AIResult, TextPart
from app.modules.ai.followup_template import facts_as_prompt_text
from app.modules.ai.prompts import followup_letter_v1, reply_classification_v1
from app.modules.ai.schemas import FollowupProse, ReplyClassification

CLASSIFY_PROMPT_VERSION = reply_classification_v1.PROMPT_VERSION
FOLLOWUP_PROMPT_VERSION = followup_letter_v1.PROMPT_VERSION
MAX_TOKENS = 8000
MAX_REPLY_CHARS = 8000  # longer replies are cut; the citizen can always read the full text


def _escape(text: str) -> str:
    # The reply can't close our tags: "<" becomes a harmless look-alike escape.
    return text.replace("<", "\u003c")


def classify_reply(
    provider: AIProvider, *, subject: str, body: str, own_reference: str
) -> AIResult[ReplyClassification]:
    content = (
        f"<complaint_reference>{_escape(own_reference)}</complaint_reference>\n"
        f"<reply>\nSubject: {_escape(subject)}\n\n{_escape(body[:MAX_REPLY_CHARS])}\n</reply>\n\n"
        "Classify this reply."
    )
    return provider.generate_structured(
        task=CLASSIFY_PROMPT_VERSION,
        system_prompt=reply_classification_v1.SYSTEM_PROMPT,
        content=[TextPart(content)],
        output_schema=ReplyClassification,
        max_tokens=MAX_TOKENS,
    )


def write_followup_prose(provider: AIProvider, facts: dict[str, Any]) -> AIResult[FollowupProse]:
    return provider.generate_structured(
        task=FOLLOWUP_PROMPT_VERSION,
        system_prompt=followup_letter_v1.SYSTEM_PROMPT,
        content=[TextPart(facts_as_prompt_text(facts))],
        output_schema=FollowupProse,
        max_tokens=MAX_TOKENS,
    )

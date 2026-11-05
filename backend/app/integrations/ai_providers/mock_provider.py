"""A deterministic stand-in for a real AI model. No network, no API key, no cost.

It does NOT look at the photo: it returns a fixed sample answer for the configured scenario
(MOCK_AI_SCENARIO). Replies are "read" with simple keyword rules. Every result is flagged
`is_mock=True`, and the UI labels it "Demo AI".

Scenarios:
  pothole | streetlight | garbage | not_civic   realistic sample answers
  failure                                      the provider is "down" (AIProviderError)
  invalid                                      the answer breaks the schema (AIOutputError)

Before/after comparisons use a separate setting (MOCK_AI_RESOLUTION): resolved | not_resolved |
partial | unsure | different_place. The mock never looks at the photos.
"""

import json
import re
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from app.integrations.ai_providers.base import (
    AIOutputError,
    AIProviderError,
    AIResult,
    ContentPart,
    T,
    TextPart,
)

VISION_SAMPLES: dict[str, dict[str, Any]] = {
    "pothole": {
        "is_civic_issue": True,
        "category": "ROAD_POTHOLE",
        "category_confidence": "HIGH",
        "suggested_title": "Pothole on the road surface",
        "suggested_description": (
            "A pothole is visible on the road surface. It appears to contain standing water, "
            "and the edges of the surrounding asphalt look broken."
        ),
        "severity": "MEDIUM",
        "observations": [
            "A roughly oval hole in the asphalt",
            "Standing water inside the hole",
            "Lane markings nearby suggest a road used by traffic",
        ],
        "uncertainties": ["The depth of the pothole cannot be judged from the photo"],
        "warnings": [],
    },
    "streetlight": {
        "is_civic_issue": True,
        "category": "BROKEN_STREETLIGHT",
        "category_confidence": "MEDIUM",
        "suggested_title": "Streetlight appears to be damaged",
        "suggested_description": (
            "A streetlight is visible with what appears to be a damaged or missing lamp cover."
        ),
        "severity": "LOW",
        "observations": ["A streetlight pole", "The lamp housing appears damaged"],
        "uncertainties": ["It cannot be confirmed from a photo whether the light works at night"],
        "warnings": [],
    },
    "garbage": {
        "is_civic_issue": True,
        "category": "GARBAGE_OVERFLOW",
        "category_confidence": "HIGH",
        "suggested_title": "Overflowing garbage bins",
        "suggested_description": (
            "Garbage bins are overflowing and waste has spilled onto the ground around them."
        ),
        "severity": "MEDIUM",
        "observations": ["Bins filled beyond capacity", "Loose waste on the ground"],
        "uncertainties": ["How long the waste has been there is not visible"],
        "warnings": [],
    },
    "not_civic": {
        "is_civic_issue": False,
        "category": "OTHER",
        "category_confidence": "LOW",
        "suggested_title": "Unclear civic issue",
        "suggested_description": "No clear public infrastructure problem is visible in this photo.",
        "severity": "UNKNOWN",
        "observations": ["The photo does not clearly show a public infrastructure problem"],
        "uncertainties": ["The photo may not show the problem the reporter intended"],
        "warnings": ["Please check that you uploaded the right photo"],
    },
    # Breaks the schema on purpose (unknown category, empty title) to exercise error handling.
    "invalid": {"is_civic_issue": True, "category": "VOLCANO", "suggested_title": ""},
}

_FACTS_PATTERN = re.compile(r"<facts>\s*(\{.*\})\s*</facts>", re.DOTALL)
_REPLY_PATTERN = re.compile(r"<reply>(.*)</reply>", re.DOTALL)
_MOCK_REFERENCE = re.compile(
    r"(?i)reference (?:number )?(?:is )?([A-Z0-9][A-Z0-9/-]{2,38}[A-Z0-9])"
)

RESOLUTION_SAMPLES: dict[str, dict[str, Any]] = {
    "resolved": {
        "assessment": "APPEARS_RESOLVED",
        "confidence": "MEDIUM",
        "same_location_likely": "YES",
        "visible_changes": ["The damaged area appears to have been filled and levelled"],
        "remaining_problems": [],
        "uncertainties": ["The quality of the repair cannot be judged from a photo"],
        "summary": "The problem in the first photo appears to have been repaired in the second.",
    },
    "not_resolved": {
        "assessment": "NOT_RESOLVED",
        "confidence": "MEDIUM",
        "same_location_likely": "YES",
        "visible_changes": [],
        "remaining_problems": ["The same damage is still visible"],
        "uncertainties": [],
        "summary": "The problem shown in the first photo still appears to be there.",
    },
    "partial": {
        "assessment": "PARTIALLY_RESOLVED",
        "confidence": "LOW",
        "same_location_likely": "YES",
        "visible_changes": ["Part of the damaged area appears to have been repaired"],
        "remaining_problems": ["Some damage still appears to be visible at the edge"],
        "uncertainties": ["The photos are taken from different angles"],
        "summary": "Part of the problem appears to have been repaired, but not all of it.",
    },
    "unsure": {
        "assessment": "CANNOT_DETERMINE",
        "confidence": "LOW",
        "same_location_likely": "UNSURE",
        "visible_changes": [],
        "remaining_problems": [],
        "uncertainties": ["The second photo is too dark to compare"],
        "summary": "The photos are not clear enough to compare.",
    },
    "different_place": {
        "assessment": "CANNOT_DETERMINE",
        "confidence": "LOW",
        "same_location_likely": "NO",
        "visible_changes": [],
        "remaining_problems": [],
        "uncertainties": ["The two photos seem to show different places"],
        "summary": "The two photos do not appear to show the same place.",
    },
}

# Keyword rules for the mock's reading of a reply, checked in this order.
_REPLY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("UNRELATED", ("out of office", "automatic reply", "newsletter")),
    ("REQUEST_FOR_INFO", ("please provide", "please share", "more information", "could you send")),
    ("REJECTION", ("not under our jurisdiction", "unable to take", "rejected", "declined")),
    ("RESOLVED_CLAIM", ("resolved", "repaired", "has been fixed", "work is complete")),
    ("IN_PROGRESS", ("in progress", "work has started", "team has been assigned", "scheduled")),
    ("ACKNOWLEDGMENT", ("received", "registered", "acknowledge")),
]


class MockAIProvider:
    name = "mock"
    model = "mock-v1"
    is_mock = True

    def __init__(self, scenario: str = "pothole", resolution_scenario: str = "resolved") -> None:
        self.scenario = scenario
        self.resolution_scenario = resolution_scenario

    def generate_structured(
        self,
        *,
        task: str,
        system_prompt: str,
        content: Sequence[ContentPart],
        output_schema: type[T],
        max_tokens: int,
    ) -> AIResult[T]:
        if self.scenario == "failure":
            raise AIProviderError("The mock AI provider is simulating an outage.")

        if task.startswith("vision"):
            raw: dict[str, Any] = VISION_SAMPLES.get(self.scenario, VISION_SAMPLES["pothole"])
        elif task.startswith("complaint_letter"):
            raw = self._letter_sample(content)
        elif task.startswith("reply_classification"):
            raw = self._reply_sample(content)
        elif task.startswith("followup_letter"):
            raw = self._followup_sample(content)
        elif task.startswith("resolution"):
            raw = (
                {"assessment": "FIXED"}
                if self.scenario == "invalid"
                else RESOLUTION_SAMPLES[self.resolution_scenario]
            )
        else:
            raise AIProviderError(f"The mock has no sample answer for task {task!r}.")

        try:
            output = output_schema.model_validate(raw)
        except ValidationError as exc:
            raise AIOutputError(
                f"Mock output failed validation: {exc.error_count()} error(s)"
            ) from exc
        return AIResult(
            output=output, provider=self.name, model=self.model, is_mock=True, latency_ms=0
        )

    def _letter_sample(self, content: Sequence[ContentPart]) -> dict[str, Any]:
        if self.scenario == "invalid":
            return {"subject": ""}
        # The letter agent sends the confirmed facts as JSON; the mock reuses them so its
        # sample letter mentions the right issue. (A real model reads the same facts.)
        facts: dict[str, Any] = {}
        for part in content:
            if isinstance(part, TextPart) and (match := _FACTS_PATTERN.search(part.text)):
                facts = json.loads(match.group(1))
        issue = facts.get("category_label", "civic issue").lower()
        place = facts.get("location_summary", "the reported location")
        return {
            "subject": f"Request for action: {facts.get('title', 'reported civic issue')}",
            "issue_summary": (
                f"I am writing to report a {issue} at {place}. "
                f"{facts.get('citizen_description', '')}".strip()
            ),
            "requested_action": (
                "I kindly request that the responsible team inspect the site and carry out the "
                "necessary repairs at the earliest opportunity."
            ),
        }

    def _reply_sample(self, content: Sequence[ContentPart]) -> dict[str, Any]:
        if self.scenario == "invalid":
            return {"kind": "MAYBE"}
        text = ""
        for part in content:
            if isinstance(part, TextPart) and (match := _REPLY_PATTERN.search(part.text)):
                text = match.group(1)
        lowered = text.lower()
        kind = next(
            (k for k, words in _REPLY_RULES if any(word in lowered for word in words)), None
        )
        reference = _MOCK_REFERENCE.search(text)
        return {
            "kind": kind or "UNRELATED",
            "confidence": "HIGH" if kind else "LOW",
            "reference_number": reference.group(1) if reference else None,
            "summary": (
                f"Demo reading: the reply looks like a {kind.lower().replace('_', ' ')} message."
                if kind
                else "Demo reading: the meaning of this reply is unclear."
            ),
        }

    def _followup_sample(self, content: Sequence[ContentPart]) -> dict[str, Any]:
        if self.scenario == "invalid":
            return {"opening": ""}
        facts: dict[str, Any] = {}
        for part in content:
            if isinstance(part, TextPart) and (match := _FACTS_PATTERN.search(part.text)):
                facts = json.loads(match.group(1))
        issue = facts.get("category_label", "civic issue").lower()
        if facts.get("department_replied"):
            opening = (
                f"Thank you for your earlier response regarding the {issue} I reported. "
                "I would be grateful to know how the work is progressing."
            )
        else:
            opening = (
                f"I am following up on my complaint about the {issue} I reported, as I have "
                "not yet received a response."
            )
        return {
            "opening": opening,
            "requested_action": (
                "Could you please let me know the current status and when the issue is "
                "expected to be addressed?"
            ),
        }

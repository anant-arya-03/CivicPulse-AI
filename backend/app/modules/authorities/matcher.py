"""Deterministic department matching. No AI: plain, testable rules.

Given an issue category and a location, rank the directory's departments:

1. Only active departments that handle the category can match.
2. Country must agree when both sides know it.
3. A department covering the same city scores highest; a state-level department in the same
   state comes next; a national one last.
4. Confidence:
   EXACT   - exactly one best match, and it covers the complaint's city
   PARTIAL - several equally good matches, or only state/national ones: the citizen must choose
   NONE    - nothing in the directory handles this

The citizen always confirms the choice; EXACT only means we can pre-select it.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from app.modules.authorities.models import Authority

Confidence = Literal["EXACT", "PARTIAL", "NONE"]

_CITY_SCORE = 10
_STATE_SCORE = 5
_NATIONAL_SCORE = 2
_VERIFIED_BONUS = 1  # tie-break: prefer records with a verified email


@dataclass
class Match:
    authority: Authority
    score: int
    reasons: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    confidence: Confidence
    matches: list[Match]  # best first


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def match_authorities(
    authorities: Iterable[Authority],
    *,
    category: str,
    city: str | None,
    state: str | None,
    country: str | None,
    category_label: str,
) -> MatchResult:
    city_n, state_n, country_n = _norm(city), _norm(state), _norm(country)
    matches: list[Match] = []

    for authority in authorities:
        if not authority.active or category not in (authority.supported_categories or []):
            continue
        if country_n and _norm(authority.country) != country_n:
            continue

        reasons = [f"Handles {category_label.lower()} issues."]
        a_city, a_state = _norm(authority.city), _norm(authority.state)
        if (
            a_city
            and city_n
            and a_city == city_n
            and (not a_state or not state_n or a_state == state_n)
        ):
            score = _CITY_SCORE
            reasons.append(f"Covers {authority.city}, where the problem is.")
        elif (
            not a_city
            and authority.jurisdiction_level == "STATE"
            and a_state
            and a_state == state_n
        ):
            score = _STATE_SCORE
            reasons.append(f"State-level department for {authority.state}.")
        elif not a_city and not a_state and authority.jurisdiction_level == "NATIONAL":
            score = _NATIONAL_SCORE
            reasons.append("National department.")
        else:
            continue  # a department for a different place

        if authority.official_email:
            score += _VERIFIED_BONUS
        else:
            reasons.append(
                "No public email address on record, so it can't receive complaints here."
            )
        matches.append(Match(authority=authority, score=score, reasons=reasons))

    matches.sort(key=lambda m: (-m.score, m.authority.name))
    if not matches:
        return MatchResult(confidence="NONE", matches=[])

    best = matches[0].score
    top = [m for m in matches if m.score == best]
    covers_city = best >= _CITY_SCORE
    confidence: Confidence = "EXACT" if len(top) == 1 and covers_city else "PARTIAL"
    if confidence == "PARTIAL" and len(top) > 1:
        for m in top:
            m.reasons.append("Several departments could handle this. Please choose one.")
    return MatchResult(confidence=confidence, matches=matches)

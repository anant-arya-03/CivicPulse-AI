"""Resolution rules on their own: warnings about uncertain comparisons, and which status changes
the citizen's decision may make."""

import pytest

from app.modules.complaints.constants import ComplaintStatus as S
from app.modules.complaints.status_machine import can_transition
from app.modules.resolutions import rules


def assessment(**overrides: str) -> dict:
    base = {"assessment": "APPEARS_RESOLVED", "confidence": "HIGH", "same_location_likely": "YES"}
    base.update(overrides)
    return base


def test_a_clear_comparison_still_says_the_ai_can_be_wrong() -> None:
    assert rules.cautions(assessment()) == [rules.ALWAYS]


def test_no_ai_means_compare_yourself() -> None:
    notes = rules.cautions(None)
    assert len(notes) == 1 and "compare the two photos yourself" in notes[0]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"same_location_likely": "NO"}, "different places"),
        ({"same_location_likely": "UNSURE"}, "couldn't tell whether both photos"),
        ({"assessment": "CANNOT_DETERMINE"}, "couldn't judge the repair"),
        ({"assessment": "PARTIALLY_RESOLVED"}, "may be incomplete"),
        ({"assessment": "NOT_RESOLVED"}, "may still be there"),
        ({"confidence": "LOW"}, "not confident"),
    ],
)
def test_uncertainty_is_spelled_out(overrides: dict, expected: str) -> None:
    notes = rules.cautions(assessment(**overrides))
    assert any(expected in note for note in notes)
    assert notes[-1] == rules.ALWAYS


def test_confirming_a_claimed_repair() -> None:
    assert rules.transitions_for("CONFIRMED_RESOLVED", S.RESOLVED_PENDING_VERIFICATION) == [
        S.VERIFIED_RESOLVED
    ]


@pytest.mark.parametrize("status", [S.SUBMITTED, S.ACKNOWLEDGED, S.IN_PROGRESS, S.REOPENED])
def test_confirming_a_fix_the_citizen_found_goes_through_pending_verification(status: S) -> None:
    assert rules.transitions_for("CONFIRMED_RESOLVED", status) == [
        S.RESOLVED_PENDING_VERIFICATION,
        S.VERIFIED_RESOLVED,
    ]


def test_disputing_needs_a_claimed_repair() -> None:
    assert rules.transitions_for("DISPUTED", S.RESOLVED_PENDING_VERIFICATION) == [S.REOPENED]
    for status in (S.SUBMITTED, S.ACKNOWLEDGED, S.IN_PROGRESS, S.REOPENED):
        assert rules.transitions_for("DISPUTED", status) is None


@pytest.mark.parametrize("decision", ["CONFIRMED_RESOLVED", "DISPUTED"])
@pytest.mark.parametrize("status", list(S))
def test_every_decision_follows_the_status_machine(decision: rules.Decision, status: S) -> None:
    steps = rules.transitions_for(decision, status)
    if steps is None:
        return
    current = status
    for target in steps:
        assert can_transition(current, target), (current, target)
        current = target


@pytest.mark.parametrize(
    "status", [S.DRAFT, S.PENDING_REVIEW, S.VERIFIED_RESOLVED, S.CLOSED, S.CANCELLED]
)
def test_no_decision_outside_the_checking_window(status: S) -> None:
    assert rules.transitions_for("CONFIRMED_RESOLVED", status) is None
    assert rules.transitions_for("DISPUTED", status) is None

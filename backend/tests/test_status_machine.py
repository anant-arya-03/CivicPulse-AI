"""Every possible (from, to) status pair is checked against the documented lifecycle
(docs/workflows.md section 1). If you change the lifecycle, update EXPECTED here too."""

import itertools

import pytest

from app.core.errors import InvalidTransitionError
from app.modules.complaints.constants import ComplaintStatus as S
from app.modules.complaints.status_machine import (
    ALLOWED_TRANSITIONS,
    can_transition,
    ensure_transition,
)

# Written out independently of the implementation, so a typo in either one is caught.
EXPECTED: dict[S, set[S]] = {
    S.DRAFT: {S.PENDING_REVIEW, S.CANCELLED},
    S.PENDING_REVIEW: {S.DRAFT, S.SUBMITTED, S.CANCELLED},
    S.SUBMITTED: {
        S.ACKNOWLEDGED,
        S.IN_PROGRESS,
        S.RESOLVED_PENDING_VERIFICATION,
        S.CLOSED,
        S.CANCELLED,
    },
    S.ACKNOWLEDGED: {S.IN_PROGRESS, S.RESOLVED_PENDING_VERIFICATION, S.CLOSED},
    S.IN_PROGRESS: {S.RESOLVED_PENDING_VERIFICATION, S.CLOSED},
    S.RESOLVED_PENDING_VERIFICATION: {S.VERIFIED_RESOLVED, S.REOPENED},
    S.VERIFIED_RESOLVED: {S.CLOSED, S.REOPENED},
    S.REOPENED: {S.ACKNOWLEDGED, S.IN_PROGRESS, S.RESOLVED_PENDING_VERIFICATION, S.CLOSED},
    S.CLOSED: {S.REOPENED},
    S.CANCELLED: set(),
}

ALL_PAIRS = list(itertools.product(S, S))
ALLOWED_PAIRS = [(a, b) for a, b in ALL_PAIRS if b in EXPECTED[a]]
FORBIDDEN_PAIRS = [(a, b) for a, b in ALL_PAIRS if b not in EXPECTED[a]]


def test_every_status_has_a_rule() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(S)
    assert set(EXPECTED) == set(S)


@pytest.mark.parametrize(("current", "new"), ALLOWED_PAIRS, ids=lambda s: s.value)
def test_allowed_transition(current: S, new: S) -> None:
    assert can_transition(current, new)
    ensure_transition(current, new)  # does not raise


@pytest.mark.parametrize(("current", "new"), FORBIDDEN_PAIRS, ids=lambda s: s.value)
def test_forbidden_transition(current: S, new: S) -> None:
    assert not can_transition(current, new)
    with pytest.raises(InvalidTransitionError) as exc_info:
        ensure_transition(current, new)
    assert exc_info.value.details == {
        "current_status": current.value,
        "requested_status": new.value,
    }


def test_no_status_can_transition_to_itself() -> None:
    assert all(not can_transition(s, s) for s in S)


def test_cancelled_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS[S.CANCELLED] == frozenset()


def test_transition_counts() -> None:
    # 10 statuses x 10 = 100 pairs; the lifecycle allows exactly 24 of them.
    assert len(ALL_PAIRS) == 100
    assert len(ALLOWED_PAIRS) == 24

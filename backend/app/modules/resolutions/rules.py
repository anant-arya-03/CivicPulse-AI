"""Resolution rules as plain functions (no database, no AI), each with a simple test.

The AI's comparison is advice. These rules turn its uncertainty into plain warnings, and decide
which status changes the CITIZEN's decision may make.
"""

from typing import Any, Literal

from app.modules.complaints.constants import MONITORED_STATUSES
from app.modules.complaints.constants import ComplaintStatus as S

Decision = Literal["CONFIRMED_RESOLVED", "DISPUTED"]

ALWAYS = "The AI can be wrong. Only your own check decides."


def cautions(assessment: dict[str, Any] | None) -> list[str]:
    """Warnings to show next to the AI's comparison (or its absence)."""
    if assessment is None:
        return ["The AI comparison isn't available. Please compare the two photos yourself."]
    notes: list[str] = []
    location = assessment.get("same_location_likely")
    if location == "NO":
        notes.append(
            "The AI thinks the photos may show different places. Check that the new photo "
            "shows the same spot."
        )
    elif location == "UNSURE":
        notes.append("The AI couldn't tell whether both photos show the same place.")
    result = assessment.get("assessment")
    if result == "CANNOT_DETERMINE":
        notes.append("The AI couldn't judge the repair from these photos.")
    elif result == "PARTIALLY_RESOLVED":
        notes.append("The AI thinks the repair may be incomplete.")
    elif result == "NOT_RESOLVED":
        notes.append("The AI thinks the problem may still be there.")
    if assessment.get("confidence") == "LOW":
        notes.append("The AI is not confident about this comparison.")
    notes.append(ALWAYS)
    return notes


def transitions_for(decision: Decision, status: S) -> list[S] | None:
    """The status changes a decision makes, in order, or None if it isn't allowed now.

    - Confirming: from "awaiting your verification" straight to verified. While still waiting
      for the department, the citizen may also confirm a fix they found themselves (recorded
      as "reported fixed", then verified), using only transitions the status machine allows.
    - Disputing: only a repair the department claimed, which reopens the complaint.
    """
    if decision == "CONFIRMED_RESOLVED":
        if status == S.RESOLVED_PENDING_VERIFICATION:
            return [S.VERIFIED_RESOLVED]
        if status in MONITORED_STATUSES:
            return [S.RESOLVED_PENDING_VERIFICATION, S.VERIFIED_RESOLVED]
        return None
    if status == S.RESOLVED_PENDING_VERIFICATION:
        return [S.REOPENED]
    return None

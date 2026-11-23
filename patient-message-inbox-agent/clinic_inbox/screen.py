"""Conservative lexical screen for synthetic course fixtures."""

import re
import unicodedata

PATTERNS = (
    r"\bchest\b.{0,24}\b(pain|pressure|tight|tightness|crushing)\b",
    r"\b(pressure|tightness|crushing|pain)\b.{0,22}\bchest\b",
    r"\b(can(?:no|')t|unable to|struggl\w* to|hard to)\s+(?:catch my breath|breathe)",
    r"\b(shortness of breath|gasping|breathless at rest)\b",
    r"\b(saa?ns|saans)\b.{0,36}\b(takleef|dikkat|mushkil)\b",
    r"\b(face|facial|mouth)\b.{0,25}\bdroop\w*|\b(slurred? speech|speech is slurred)\b",
    r"\b(fainted|passed out|unconscious|blacked out)\b",
    r"\b(suicid\w*|ending my life|kill myself|hurt myself)\b",
)
WARNING = re.compile("|".join(f"(?:{p})" for p in PATTERNS), re.IGNORECASE)
URGENT_REPLY = (
    "Your message needs urgent nurse review. If you think this may be an emergency, "
    "contact your local emergency services or go to the nearest emergency department now."
)


def screen(text):
    normalized = unicodedata.normalize("NFKC", text).replace("’", "'")
    return bool(WARNING.search(" ".join(normalized.split())))

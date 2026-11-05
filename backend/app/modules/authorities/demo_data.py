"""FICTIONAL demo departments for "Demo City, Demo State" (country XX).

They match the mock geocoder's sample places and exist only so the workflow can be demonstrated.
Every record:
- has is_demo = True (the UI shows "Demo directory entry"),
- uses an .example email address (reserved by RFC 2606, so mail can never be delivered),
- has no phone number and no source URL (there is no real source).

Real departments are added with scripts/import_authorities.py from verified official sources.
"""

from typing import Any

_COMMON: dict[str, Any] = {
    "country": "XX",
    "is_demo": True,
    "verification_notes": "Fictional record for demonstrations. Not a real government contact.",
}

COMMISSIONER = "Demo City Municipal Commissioner's Office"

DEMO_AUTHORITIES: list[dict[str, Any]] = [
    {
        **_COMMON,
        "name": COMMISSIONER,
        "jurisdiction": "Demo City (escalation office)",
        "jurisdiction_level": "CITY",
        "city": "Demo City",
        "state": "Demo State",
        "supported_categories": [],  # escalation only: never matched directly
        "official_email": "commissioner@demo-city.example",
    },
    {
        **_COMMON,
        "name": "Demo City Roads and Infrastructure Department",
        "jurisdiction": "Demo City",
        "jurisdiction_level": "CITY",
        "city": "Demo City",
        "state": "Demo State",
        "supported_categories": ["ROAD_POTHOLE", "DAMAGED_INFRASTRUCTURE"],
        "official_email": "roads@demo-city.example",
        "service_timeline_days": 7,
        "parent": COMMISSIONER,
    },
    {
        **_COMMON,
        "name": "Demo City Street Lighting Department",
        "jurisdiction": "Demo City",
        "jurisdiction_level": "CITY",
        "city": "Demo City",
        "state": "Demo State",
        "supported_categories": ["BROKEN_STREETLIGHT"],
        "official_email": "streetlights@demo-city.example",
        "parent": COMMISSIONER,
    },
    {
        **_COMMON,
        "name": "Demo City Solid Waste Management Department",
        "jurisdiction": "Demo City",
        "jurisdiction_level": "CITY",
        "city": "Demo City",
        "state": "Demo State",
        "supported_categories": ["GARBAGE_OVERFLOW"],
        "official_email": "waste@demo-city.example",
        "parent": COMMISSIONER,
    },
    {
        **_COMMON,
        "name": "Demo City Water Supply and Sewerage Board",
        "jurisdiction": "Demo City",
        "jurisdiction_level": "CITY",
        "city": "Demo City",
        "state": "Demo State",
        "supported_categories": ["WATER_LEAKAGE", "OPEN_DRAIN", "WATERLOGGING"],
        "official_email": "water@demo-city.example",
        "parent": COMMISSIONER,
    },
    {
        # Overlaps with the water board on purpose, to demonstrate "please choose" matches.
        **_COMMON,
        "name": "Demo City Storm Water Drains Cell",
        "jurisdiction": "Demo City",
        "jurisdiction_level": "CITY",
        "city": "Demo City",
        "state": "Demo State",
        "supported_categories": ["WATERLOGGING", "OPEN_DRAIN"],
        "official_email": "drains@demo-city.example",
        "parent": COMMISSIONER,
    },
    {
        # State-level fallback for other towns in Demo State.
        **_COMMON,
        "name": "Demo State Public Works Department",
        "jurisdiction": "Demo State",
        "jurisdiction_level": "STATE",
        "city": None,
        "state": "Demo State",
        "supported_categories": ["ROAD_POTHOLE", "DAMAGED_INFRASTRUCTURE"],
        "official_email": "pwd@demo-state.example",
    },
]

"""Offline geocoder with a few FICTIONAL places in "Demo City" (country code XX, which ISO 3166
reserves for user-defined use, so it can never be mistaken for a real country).

Used in tests and when no network is available. The frontend shows a "sample locations" note
whenever this provider is active.
"""

from app.integrations.geocoding.base import GeocodeResult


def _place(address: str, locality: str, lat: float, lon: float) -> GeocodeResult:
    return GeocodeResult(
        label=f"{address}, {locality}, Demo City, Demo State 100001 (sample)",
        address_line=address,
        locality=locality,
        city="Demo City",
        state="Demo State",
        postal_code="100001",
        country="XX",
        latitude=lat,
        longitude=lon,
    )


SAMPLE_PLACES = [
    _place("12 Market Street", "Central Ward", 0.0102, 0.0105),
    _place("45 Lake Road", "Lakeside", 0.0151, 0.0098),
    _place("7 Station Avenue", "Railway Colony", 0.0088, 0.0152),
    _place("Ring Road Junction", "North Ward", 0.0193, 0.0121),
]


class MockGeocoder:
    name = "mock"

    def search(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        words = [w for w in query.lower().split() if len(w) > 1]
        matches = [place for place in SAMPLE_PLACES if any(w in place.label.lower() for w in words)]
        return (matches or SAMPLE_PLACES)[:limit]

    def reverse(self, latitude: float, longitude: float) -> GeocodeResult:
        return GeocodeResult(
            label=f"Pinned location near {latitude:.5f}, {longitude:.5f}, Demo City (sample)",
            address_line=f"Near {latitude:.5f}, {longitude:.5f}",
            locality=None,
            city="Demo City",
            state="Demo State",
            postal_code=None,
            country="XX",
            latitude=latitude,
            longitude=longitude,
        )

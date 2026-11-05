"""The geocoding interface: turn an address into coordinates (search) and back (reverse)."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeocodeResult:
    label: str  # full human-readable address
    address_line: str | None
    locality: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None  # ISO 3166 alpha-2, upper case
    latitude: float
    longitude: float


class GeocodingError(Exception):
    """The geocoding service could not be reached or returned something unusable."""


class Geocoder(Protocol):
    name: str

    def search(self, query: str, limit: int = 5) -> list[GeocodeResult]: ...

    def reverse(self, latitude: float, longitude: float) -> GeocodeResult | None: ...

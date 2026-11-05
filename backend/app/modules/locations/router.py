"""Address search for the report form. The browser never talks to the geocoding service
directly; going through the backend lets us enforce usage limits and swap providers."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.errors import ServiceUnavailableError
from app.core.rate_limit import RateLimit
from app.integrations.geocoding.base import Geocoder, GeocodingError
from app.integrations.geocoding.factory import get_geocoder
from app.modules.auth.dependencies import CurrentUser

router = APIRouter(
    prefix="/locations",
    tags=["locations"],
    dependencies=[Depends(RateLimit("locations", times=30, seconds=60))],
)

GeocoderDep = Annotated[Geocoder, Depends(get_geocoder)]
_UNAVAILABLE = "Address search is unavailable right now. You can still type the address."


class LocationResult(BaseModel):
    label: str
    address_line: str | None
    locality: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    latitude: float
    longitude: float


class LocationSearchResponse(BaseModel):
    provider: str  # "mock" means sample data; the UI tells the user
    results: list[LocationResult]


class ReverseGeocodeResponse(BaseModel):
    provider: str
    result: LocationResult | None


@router.get("/search", response_model=LocationSearchResponse)
def search_locations(
    _: CurrentUser,
    geocoder: GeocoderDep,
    q: Annotated[str, Query(min_length=3, max_length=200)],
):
    try:
        results = geocoder.search(q.strip())
    except GeocodingError:
        raise ServiceUnavailableError(_UNAVAILABLE) from None
    return LocationSearchResponse(
        provider=geocoder.name, results=[LocationResult(**asdict(r)) for r in results]
    )


@router.get("/reverse", response_model=ReverseGeocodeResponse)
def reverse_geocode(
    _: CurrentUser,
    geocoder: GeocoderDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
):
    try:
        result = geocoder.reverse(lat, lon)
    except GeocodingError:
        raise ServiceUnavailableError(_UNAVAILABLE) from None
    return ReverseGeocodeResponse(
        provider=geocoder.name, result=LocationResult(**asdict(result)) if result else None
    )

"""Geocoding with OpenStreetMap's free Nominatim service.

Nominatim's usage policy (https://operations.osmfoundation.org/policies/nominatim/) asks us to:
- send at most 1 request per second       -> `_throttle()`
- identify the app with a User-Agent        -> NOMINATIM_USER_AGENT (checked in config.py)
- cache results                             -> `_cache`
- not use it for autocomplete               -> the frontend only searches when the user submits
For heavy production traffic, switch to a paid provider or run your own Nominatim server.
"""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from typing import Any

from app.integrations.geocoding.base import GeocodeResult, GeocodingError

_MIN_SECONDS_BETWEEN_REQUESTS = 1.0
_CACHE_SIZE = 256
_TIMEOUT_SECONDS = 8


class NominatimGeocoder:
    name = "nominatim"

    def __init__(self, base_url: str, user_agent: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._cache: OrderedDict[str, Any] = OrderedDict()

    def search(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        data = self._get("search", {"q": query, "limit": str(limit)})
        if not isinstance(data, list):
            raise GeocodingError("Unexpected search response.")
        return [r for r in (parse_place(item) for item in data) if r is not None]

    def reverse(self, latitude: float, longitude: float) -> GeocodeResult | None:
        data = self._get("reverse", {"lat": f"{latitude:.6f}", "lon": f"{longitude:.6f}"})
        if not isinstance(data, dict) or "error" in data:
            return None
        return parse_place(data)

    def _get(self, endpoint: str, params: dict[str, str]) -> Any:
        query = urllib.parse.urlencode(
            {**params, "format": "jsonv2", "addressdetails": "1", "accept-language": "en"}
        )
        url = f"{self.base_url}/{endpoint}?{query}"
        with self._lock:
            if url in self._cache:
                self._cache.move_to_end(url)
                return self._cache[url]
            self._throttle()
            request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            try:
                with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                    data = json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                raise GeocodingError(str(exc)) from exc
            self._cache[url] = data
            if len(self._cache) > _CACHE_SIZE:
                self._cache.popitem(last=False)
            return data

    def _throttle(self) -> None:
        wait = self._last_request_at + _MIN_SECONDS_BETWEEN_REQUESTS - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()


def parse_place(item: dict[str, Any]) -> GeocodeResult | None:
    """Convert one Nominatim result into our GeocodeResult (public for unit testing)."""
    try:
        latitude, longitude = float(item["lat"]), float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    address: dict[str, str] = item.get("address") or {}

    def first(*keys: str) -> str | None:
        return next((address[k] for k in keys if address.get(k)), None)

    road = first("road", "pedestrian", "footway", "street")
    house = address.get("house_number")
    address_line = f"{house} {road}" if house and road else road or item.get("name") or None
    country = address.get("country_code")

    return GeocodeResult(
        label=item.get("display_name") or address_line or f"{latitude}, {longitude}",
        address_line=address_line,
        locality=first("suburb", "neighbourhood", "quarter", "city_district"),
        city=first("city", "town", "village", "municipality", "county"),
        state=first("state", "state_district", "region"),
        postal_code=address.get("postcode"),
        country=country.upper() if country else None,
        latitude=latitude,
        longitude=longitude,
    )

from functools import lru_cache

from app.core.config import get_settings
from app.integrations.geocoding.base import Geocoder
from app.integrations.geocoding.mock_geocoder import MockGeocoder
from app.integrations.geocoding.nominatim_geocoder import NominatimGeocoder


@lru_cache
def get_geocoder() -> Geocoder:
    """FastAPI dependency returning the configured geocoder (GEOCODER=mock|nominatim)."""
    settings = get_settings()
    if settings.geocoder == "nominatim":
        return NominatimGeocoder(settings.nominatim_base_url, settings.nominatim_user_agent)
    return MockGeocoder()

from fastapi.testclient import TestClient

from app.integrations.geocoding.nominatim_geocoder import parse_place
from tests.conftest import register


def test_search_requires_login(client: TestClient) -> None:
    assert client.get("/api/v1/locations/search?q=market").status_code == 401


def test_mock_search(client: TestClient) -> None:
    register(client)
    body = client.get("/api/v1/locations/search?q=lake road").json()
    assert body["provider"] == "mock"
    assert body["results"][0]["address_line"] == "45 Lake Road"
    assert body["results"][0]["country"] == "XX"


def test_search_query_too_short(client: TestClient) -> None:
    register(client)
    assert client.get("/api/v1/locations/search?q=ab").status_code == 422


def test_mock_reverse(client: TestClient) -> None:
    register(client)
    body = client.get("/api/v1/locations/reverse?lat=0.0151&lon=0.0098").json()
    assert body["result"]["city"] == "Demo City"
    assert body["result"]["latitude"] == 0.0151


def test_reverse_rejects_invalid_coordinates(client: TestClient) -> None:
    register(client)
    assert client.get("/api/v1/locations/reverse?lat=100&lon=0").status_code == 422


# The real Nominatim service is not called in tests (it is an external service with a strict
# usage policy). Instead, we check that a response in Nominatim's documented format is parsed.
def test_parse_nominatim_place() -> None:
    result = parse_place(
        {
            "lat": "12.9716",
            "lon": "77.5946",
            "display_name": "221 MG Road, Ashok Nagar, Bengaluru, Karnataka, 560001, India",
            "address": {
                "house_number": "221",
                "road": "MG Road",
                "suburb": "Ashok Nagar",
                "city": "Bengaluru",
                "state": "Karnataka",
                "postcode": "560001",
                "country_code": "in",
            },
        }
    )
    assert result is not None
    assert result.address_line == "221 MG Road"
    assert (result.locality, result.city, result.state) == ("Ashok Nagar", "Bengaluru", "Karnataka")
    assert (result.postal_code, result.country) == ("560001", "IN")
    assert (result.latitude, result.longitude) == (12.9716, 77.5946)


def test_parse_nominatim_place_falls_back_to_town() -> None:
    result = parse_place({"lat": "1", "lon": "2", "address": {"town": "Smallville"}})
    assert result is not None
    assert result.city == "Smallville"
    assert result.address_line is None


def test_parse_nominatim_place_without_coordinates() -> None:
    assert parse_place({"display_name": "Nowhere"}) is None

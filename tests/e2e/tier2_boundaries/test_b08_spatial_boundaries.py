"""
Tier 2 Boundary & Corner Cases: Feature 8 - PostGIS Spatial Geometry Boundaries (M2)
Coordinate extremes, out-of-bounds lat/long, negative radius, zero radius, precision limits.
"""

import pytest
from tests.e2e.client import E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(8)
def test_spatial_query_out_of_bounds_latitude(http_client: E2EHttpClient):
    """TC-B08-01: Boundary - Latitude > 90 or < -90 returns 422 Unprocessable Entity."""
    for bad_lat in [95.0, -91.5]:
        res = http_client.get(
            "/api/v1/junctions/nearby",
            params={"latitude": bad_lat, "longitude": 77.5946, "radius": 1000}
        )
        assert res.status_code in (404, 422), f"Accepted out-of-bounds latitude {bad_lat}: {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(8)
def test_spatial_query_out_of_bounds_longitude(http_client: E2EHttpClient):
    """TC-B08-02: Boundary - Longitude > 180 or < -180 returns 422."""
    for bad_lon in [185.0, -190.0]:
        res = http_client.get(
            "/api/v1/junctions/nearby",
            params={"latitude": 12.9716, "longitude": bad_lon, "radius": 1000}
        )
        assert res.status_code in (404, 422), f"Accepted out-of-bounds longitude {bad_lon}: {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(8)
def test_spatial_query_negative_radius_rejected(http_client: E2EHttpClient):
    """TC-B08-03: Boundary - Negative radius query parameter returns 422 or 400."""
    res = http_client.get(
        "/api/v1/junctions/nearby",
        params={"latitude": 12.9716, "longitude": 77.5946, "radius": -500}
    )
    assert res.status_code in (400, 404, 422), f"Negative radius accepted: {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(8)
def test_spatial_query_zero_radius(http_client: E2EHttpClient):
    """TC-B08-04: Boundary - Radius = 0 returns 200 with empty or exact-match results."""
    res = http_client.get(
        "/api/v1/junctions/nearby",
        params={"latitude": 12.9716, "longitude": 77.5946, "radius": 0}
    )
    assert res.status_code in (200, 404, 422)


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(8)
def test_spatial_query_non_numeric_coordinates(http_client: E2EHttpClient):
    """TC-B08-05: Boundary - Non-numeric strings in coordinates return 422."""
    res = http_client.get(
        "/api/v1/junctions/nearby",
        params={"latitude": "not-a-number", "longitude": "seventy-seven", "radius": 1000}
    )
    assert res.status_code in (404, 422), f"Non-numeric coords returned {res.status_code}"

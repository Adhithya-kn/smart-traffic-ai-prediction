"""
tests/test_api_integration_live.py - Separately Controlled Integration Tests for Real External APIs
Executes live network requests against Open-Meteo, TomTom, and Google Maps endpoints.
Separately controlled: skipped by default in sandboxed / unit testing runs.
Enabled by setting environment variable RUN_LIVE_API_TESTS=1.
"""

import os
import pytest

from traffic_system.integrations.weather_client import WeatherClient
from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.google_maps_client import GoogleMapsClient
from traffic_system.integrations.health_checker import IntegrationHealthChecker
from traffic_system.core.entities import DataProvenance

RUN_LIVE = os.environ.get("RUN_LIVE_API_TESTS", "").lower() in ("1", "true", "yes")
INTEGRATION_TIMEOUT = float(os.environ.get("INTEGRATION_TEST_TIMEOUT", "6.0"))


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Live external API integration tests run when RUN_LIVE_API_TESTS=1")
def test_live_open_meteo_endpoint_real_request():
    """Performs real un-mocked HTTP call to Open-Meteo live forecast API with configurable timeout."""
    client = WeatherClient(timeout=INTEGRATION_TIMEOUT)
    reading = client.get_weather(lat=12.9716, lon=77.5946, force_refresh=True)

    if not reading["is_live"]:
        # Environment is sandboxed or network disabled
        assert reading["is_historical_fallback"] is True
        assert reading["provenance"] == DataProvenance.HISTORICAL_DATASET.value
        assert "Empirical" in reading["source"]
        pytest.skip("Outbound network disabled or blocked by sandbox; verified graceful empirical fallback.")

    assert reading["is_live"] is True
    assert reading["is_cached"] is False
    assert reading["is_historical_fallback"] is False
    assert reading["provenance"] == DataProvenance.OPEN_METEO_LIVE_API.value
    assert "Open-Meteo" in reading["source"]
    assert -20.0 <= reading["temperature"] <= 55.0
    assert reading["condition"] in ("Clear", "Overcast", "Rainy", "Foggy")
    assert client.currently_reachable is True
    assert client.supplying_data is True
    assert client.last_successful_retrieval is not None


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Live external API integration tests run when RUN_LIVE_API_TESTS=1")
def test_live_tomtom_real_request():
    """Performs real call to TomTom Traffic API if non-empty key is present in environment with configurable timeout."""
    key = os.environ.get("TOMTOM_API_KEY", "").strip()
    if not key or len(key) < 12:
        pytest.skip("No valid TOMTOM_API_KEY provided for live integration testing.")

    client = TomTomClient(api_key=key, timeout=INTEGRATION_TIMEOUT)
    ok, msg, lat = client.test_connection()
    if not ok:
        pytest.skip(f"Live TomTom endpoint unreachable or unauthorized: {msg}")

    assert ok is True
    assert lat > 0.0
    assert client.currently_reachable is True

    flow = client.get_flow_segment(12.9756, 77.6066)
    assert flow is not None
    assert client.supplying_data is True
    assert "currentSpeed" in flow


@pytest.mark.integration
@pytest.mark.skipif(not RUN_LIVE, reason="Live external API integration tests run when RUN_LIVE_API_TESTS=1")
def test_live_google_maps_real_request():
    """Performs real call to Google Maps Platform if non-empty key is present in environment with configurable timeout."""
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key or len(key) < 12:
        pytest.skip("No valid GOOGLE_MAPS_API_KEY provided for live integration testing.")

    client = GoogleMapsClient(api_key=key, timeout=INTEGRATION_TIMEOUT)
    ok, msg, lat = client.test_connection()
    if not ok:
        pytest.skip(f"Live Google Maps endpoint unreachable or unauthorized: {msg}")

    assert ok is True
    assert client.currently_reachable is True

    places = client.search_places("MG Road Bengaluru")
    assert len(places) > 0
    assert client.supplying_data is True

"""
tests/test_api_connections.py - Unit Tests for External API Integrations
"""

from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.weather_client import WeatherClient
from traffic_system.integrations.health_checker import IntegrationHealthChecker
from traffic_system.integrations.api_manager import APIManager


def test_tomtom_key_masking_and_configuration():
    client = TomTomClient(api_key="1234567890abcdef1234567890")
    assert client.is_configured() is True
    masked = client.get_masked_key()
    assert masked.startswith("****")
    assert "1234567890abcdef" not in masked
    assert masked.endswith("7890")

    # Unconfigured key
    unconf_client = TomTomClient(api_key="")
    assert unconf_client.is_configured() is False
    assert unconf_client.get_masked_key() == ""


def test_weather_client_baseline_fallback():
    # Invalid endpoint to trigger offline fallback
    weather = WeatherClient(base_url="http://invalid.unresolvable.domain.local/forecast")
    data = weather.get_weather()
    assert "condition" in data
    assert "temperature" in data
    assert data["is_live"] is False
    assert data["provenance"] == "Historical dataset"


def test_api_manager_configuration_updates():
    mgr = APIManager()
    ok, msg, data = mgr.update_tomtom_config("new_test_tomtom_key_abcdef123456")
    assert ok is True
    assert data["configured"] is True
    assert "new_test" not in data["masked_key"]

    ok, msg, wdata = mgr.update_weather_config(api_key="optional_weather_key")
    assert ok is True

    providers = mgr.get_providers()
    assert len(providers["providers"]) == 2


def test_integration_health_checker_report():
    tomtom = TomTomClient(api_key="")
    weather = WeatherClient()
    checker = IntegrationHealthChecker(tomtom, weather)
    report = checker.check_all()

    assert "tomtom" in report
    assert "weather" in report
    assert "summary" in report
    assert "timestamp" in report

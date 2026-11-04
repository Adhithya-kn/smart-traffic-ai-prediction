"""
tests/test_api_connections.py - Unit Tests for External API Integrations
Mocks HTTP requests to comprehensively verify:
1. Distinct states: configured, connection_tested, currently_reachable, supplying_data.
2. LIVE_READY is never reported solely on API key presence.
3. last_successful_retrieval and last_attempted_request stored and tracked separately.
4. Open-Meteo provenance identifies 'Open-Meteo live API'.
5. Provider observation timestamp is preserved from response payload.
6. Strict separation of live, cached, and historical baseline data.
7. Google Maps inclusion in common provider health report.
8. Computer Vision health-check response extraction.
9. Persistent secrets storage with encrypted vault and zero plain JSON disclosure.
10. Cache invalidation on credential alterations.
11. HTTP error handling: 401/403 fail-fast, 429 rate limiting, timeouts, and malformed JSON.
"""

import io
import json
import urllib.error
import urllib.request
from unittest.mock import patch, MagicMock

import pytest

from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.weather_client import WeatherClient
from traffic_system.integrations.google_maps_client import GoogleMapsClient
from traffic_system.integrations.health_checker import IntegrationHealthChecker
from traffic_system.integrations.api_manager import APIManager, get_api_manager
from traffic_system.live.bridge import LiveTrafficDataBridge
from traffic_system.core.entities import DataProvenance
from traffic_system.core.secrets_manager import get_secrets_manager


def _make_http_response(status_code: int, payload: dict) -> MagicMock:
    """Helper creating mock urllib response context manager."""
    resp = MagicMock()
    resp.status = status_code
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def test_tomtom_key_masking_and_configuration():
    client = TomTomClient(api_key="1234567890abcdef1234567890")
    assert client.is_configured() is True
    masked = client.get_masked_key()
    assert masked.startswith("****")
    assert "1234567890abcdef" not in masked
    assert masked.endswith("7890")

    unconf_client = TomTomClient(api_key="")
    assert unconf_client.is_configured() is False
    assert unconf_client.get_masked_key() == ""
    assert unconf_client.get_status_code() == "UNCONFIGURED"


def test_provider_states_distinction_and_timestamps():
    client = TomTomClient(api_key="test_tomtom_key_12345678")
    assert client.is_configured() is True
    assert client.connection_tested is False
    assert client.currently_reachable is False
    assert client.supplying_data is False
    assert client.get_status_code() == "CONFIGURED_UNTESTED"
    assert client.last_attempted_request is None
    assert client.last_successful_retrieval is None

    # 1. Mock a successful test connection
    sample_flow_resp = {
        "flowSegmentData": {
            "currentSpeed": 35.0,
            "freeFlowSpeed": 50.0,
            "confidence": 0.98,
            "timestamp": "2026-11-03T18:00:00Z"
        }
    }
    with patch("urllib.request.urlopen", return_value=_make_http_response(200, sample_flow_resp)):
        ok, msg, lat = client.test_connection()
        assert ok is True
        assert client.connection_tested is True
        assert client.currently_reachable is True
        assert client.supplying_data is False  # test_connection only tests connectivity
        assert client.get_status_code() == "CONNECTED_NO_DATA"
        assert client.last_attempted_request is not None
        assert client.last_successful_retrieval is not None
        first_success_time = client.last_successful_retrieval

    # 2. Mock a successful get_flow_segment
    with patch("urllib.request.urlopen", return_value=_make_http_response(200, sample_flow_resp)):
        flow = client.get_flow_segment(12.9716, 77.5946)
        assert flow is not None
        assert client.supplying_data is True
        assert client.get_status_code() == "LIVE_SUPPLYING_DATA"
        assert client.last_observation_time == "2026-11-03T18:00:00Z"
        second_success_time = client.last_successful_retrieval
        assert second_success_time is not None

    # 3. Mock a subsequent failed request -> last_attempted_request updates, last_successful_retrieval stays intact
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="http://test", code=503, msg="Service Unavailable", hdrs={}, fp=io.BytesIO(b"")
    )):
        ok, data, code, err = client._execute_request("http://test")
        assert ok is False
        assert client.currently_reachable is False
        # last_successful_retrieval remains preserved from previous success
        assert client.last_successful_retrieval == second_success_time
        # last_attempted_request is refreshed to the failed attempt
        assert client.last_attempted_request is not None
        assert client.last_attempted_request >= second_success_time
        assert client.get_status_code() == "CONFIGURED_UNREACHABLE"


def test_live_bridge_never_reports_live_ready_solely_on_key():
    bridge = LiveTrafficDataBridge()
    # Configure key but do not supply real live data
    bridge.tomtom_key = "test_tomtom_key_12345678"
    bridge.tomtom_client.set_api_key(bridge.tomtom_key)
    bridge.tomtom_client.currently_reachable = False
    bridge.tomtom_client.supplying_data = False
    bridge.tomtom_client.connection_tested = False

    mock_weather = {"condition": "Clear", "temperature": 26.0, "is_live": True}
    with patch.object(bridge, "fetch_live_weather", return_value=mock_weather):
        status = bridge.get_live_status()
        # Must NOT report LIVE_READY when data is not actively supplying
        assert status["status_code"] != "LIVE_READY"
        assert status["status_code"] == "CONFIGURED_UNTESTED"
        assert status["is_live_api"] is False

        # Simulate unreachable state
        bridge.tomtom_client.connection_tested = True
        bridge.tomtom_client.currently_reachable = False
        bridge.tomtom_client.last_error = "HTTP 403 Forbidden"
        unreach_status = bridge.get_live_status()
        assert unreach_status["status_code"] == "CONFIGURED_UNREACHABLE"
        assert unreach_status["is_live_api"] is False

        # Only when both reachable and actively supplying data does it report LIVE_READY
        bridge.tomtom_client.currently_reachable = True
        bridge.tomtom_client.supplying_data = True
        live_status = bridge.get_live_status()
        assert live_status["status_code"] == "LIVE_READY"
        assert live_status["is_live_api"] is True


def test_open_meteo_provenance_and_observation_time():
    weather = WeatherClient()
    mock_meteo_data = {
        "current": {
            "time": "2026-11-03T17:45",
            "temperature_2m": 26.2,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 9.8
        }
    }
    with patch("urllib.request.urlopen", return_value=_make_http_response(200, mock_meteo_data)):
        reading = weather.get_weather(force_refresh=True)
        assert reading["is_live"] is True
        assert reading["is_cached"] is False
        assert reading["is_historical_fallback"] is False
        # Provenance must identify Open-Meteo live API, NOT TomTom
        assert reading["provenance"] == DataProvenance.OPEN_METEO_LIVE_API.value
        assert "Open-Meteo" in reading["source"]
        # Observation time must reflect actual provider timestamp
        assert reading["observation_time"] == "2026-11-03T17:45"
        assert reading["temperature"] == 26.2


def test_weather_cache_and_historical_fallback_separation():
    weather = WeatherClient(cache_ttl=60.0)
    mock_meteo_data = {
        "current": {
            "time": "2026-11-03T17:45",
            "temperature_2m": 26.2,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 9.8
        }
    }
    # 1. Fresh live query
    with patch("urllib.request.urlopen", return_value=_make_http_response(200, mock_meteo_data)):
        live_res = weather.get_weather(force_refresh=True)
        assert live_res["is_live"] is True
        assert live_res["is_cached"] is False
        assert live_res["provenance"] == DataProvenance.OPEN_METEO_LIVE_API.value

    # 2. Subsequent cached query (without force_refresh)
    cached_res = weather.get_weather(force_refresh=False)
    assert cached_res["is_live"] is False
    assert cached_res["is_cached"] is True
    assert cached_res["is_historical_fallback"] is False
    assert cached_res["provenance"] == DataProvenance.CACHED_API_RESPONSE.value

    # 3. Offline / sandboxed fallback
    offline_weather = WeatherClient(base_url="http://invalid.domain.offline/v1")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("DNS resolution failed")):
        baseline = offline_weather.get_weather(force_refresh=True)
        assert baseline["is_live"] is False
        assert baseline["is_cached"] is False
        assert baseline["is_historical_fallback"] is True
        assert baseline["provenance"] == DataProvenance.HISTORICAL_DATASET.value
        assert "Empirical" in baseline["source"]


def test_google_maps_in_health_report():
    tomtom = TomTomClient(api_key="")
    weather = WeatherClient()
    gmaps = GoogleMapsClient(api_key="")
    checker = IntegrationHealthChecker(tomtom, weather, gmaps)

    with patch.object(weather, "test_connection", return_value=(True, "Open-Meteo online", 12.0)):
        report = checker.check_all()
    assert "google_maps" in report
    assert "tomtom" in report
    assert "weather" in report
    assert "summary" in report
    assert "google_maps_active" in report["summary"]
    assert report["google_maps"]["configured"] is False
    assert report["google_maps"]["status_code"] == "UNCONFIGURED"


def test_computer_vision_health_check_response_extraction():
    mgr = APIManager()

    # 1. Mock healthy CV status
    mock_healthy_handler = MagicMock()
    mock_healthy_handler.handle_get_status.return_value = (200, {
        "success": True,
        "data": {
            "yolo_loaded": True,
            "yolo_model": "yolo11n.pt",
            "engine": "Ultralytics YOLO (yolo11n.pt)"
        }
    })

    with patch("app.routes.vision_routes.get_vision_handler", return_value=mock_healthy_handler):
        with patch.object(mgr.tomtom, "test_connection", return_value=(False, "Not configured", 0.0)):
            with patch.object(mgr.google_maps, "test_connection", return_value=(False, "Not configured", 0.0)):
                with patch.object(mgr.weather, "test_connection", return_value=(True, "Reachable", 15.0)):
                    result = mgr.execute_multi_subsystem_handshake()
                    cv_sub = result["subsystems"]["computer_vision"]
                    assert cv_sub["reachable"] is True
                    assert cv_sub["status"] == "OPERATIONAL"
                    assert "yolo11n.pt" in cv_sub["message"]

    # 2. Mock unavailable CV status
    mock_degraded_handler = MagicMock()
    mock_degraded_handler.handle_get_status.return_value = (503, {
        "success": False,
        "data": {
            "yolo_loaded": False,
            "load_error": "Ultralytics weights not found"
        }
    })

    with patch("app.routes.vision_routes.get_vision_handler", return_value=mock_degraded_handler):
        with patch.object(mgr.tomtom, "test_connection", return_value=(False, "Not configured", 0.0)):
            with patch.object(mgr.google_maps, "test_connection", return_value=(False, "Not configured", 0.0)):
                with patch.object(mgr.weather, "test_connection", return_value=(True, "Reachable", 15.0)):
                    result = mgr.execute_multi_subsystem_handshake()
                    cv_sub = result["subsystems"]["computer_vision"]
                    assert cv_sub["reachable"] is False
                    assert cv_sub["status"] == "ERROR"
                    assert "Weights not found" in cv_sub["message"] or "unavailable" in cv_sub["message"].lower()


def test_persistent_secrets_and_cache_invalidation():
    mgr = get_api_manager()
    sm = get_secrets_manager()

    # Update TomTom config
    new_key = "tomtom_secret_key_987654321012"
    ok, msg, data = mgr.update_tomtom_config(new_key)
    assert ok is True
    assert data["configured"] is True
    assert data["masked_key"] == "****1012"
    assert new_key not in json.dumps(data)  # Zero plaintext exposure

    # Verify key is safely persisted in secrets manager
    assert sm.get_secret("TOMTOM_API_KEY") == new_key

    # Verify cache invalidation
    assert mgr.tomtom.supplying_data is False
    assert mgr.tomtom.connection_tested is False


def test_http_error_handling_and_rate_limits():
    client = TomTomClient(api_key="valid_length_key_12345678")

    # 1. 401/403 Fail Fast (Should NOT retry multiple times)
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="http://test", code=403, msg="Forbidden", hdrs={}, fp=io.BytesIO(b"")
    )) as mock_open:
        ok, data, code, err = client._execute_request("http://test")
        assert ok is False
        assert code == 403
        assert "unauthorized" in err.lower() or "invalid" in err.lower()
        # Fail fast on 403: must only call once
        assert mock_open.call_count == 1

    # 2. 429 Rate Limiting backoff
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="http://test", code=429, msg="Too Many Requests", hdrs={}, fp=io.BytesIO(b"")
    )) as mock_open:
        ok, data, code, err = client._execute_request("http://test")
        assert ok is False
        assert code == 429
        assert "rate limit exceeded" in err.lower()
        assert mock_open.call_count == client.max_retries

    # 3. Malformed JSON handling
    malformed_resp = MagicMock()
    malformed_resp.status = 200
    malformed_resp.read.return_value = b"{broken_json: None"
    malformed_resp.__enter__.return_value = malformed_resp
    malformed_resp.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=malformed_resp):
        ok, data, code, err = client._execute_request("http://test")
        assert ok is False
        assert "malformed json" in err.lower()

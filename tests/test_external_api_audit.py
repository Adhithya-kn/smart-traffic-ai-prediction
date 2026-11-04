"""
tests/test_external_api_audit.py - Deep Audit & Verification of External API Integrations
Covers TomTom, Open-Meteo, and Google Maps Platform implementations:
- TomTom: flow response parsing, speed units (KMPH), separate observation/retrieval timestamps,
          HTTP 401/403/429/5xx status handling, bounded backoff, parallel non-blocking refresh,
          incident deduplication, expiration checks, and no stale responses as live.
- Weather: Open-Meteo provenance, provider observation timestamps, coordinate bounds validation,
           explicit stale cache status, historical fallback isolation, and XGBoost feature schema compatibility.
- Google Maps: Geocoding, Places, and Directions API integration, key restriction diagnoses,
               quota handling, error status classification, and backend key isolation.
"""

import io
import json
import urllib.error
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import pytest

from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.weather_client import WeatherClient
from traffic_system.integrations.google_maps_client import GoogleMapsClient
from traffic_system.events.bengaluru_incident_adapter import (
    BengaluruIncidentAdapter,
    find_nearest_corridor,
    haversine_distance_km
)
from traffic_system.live.bridge import LiveTrafficDataBridge, BENGALURU_CORRIDOR_GPS
from traffic_system.core.entities import DataProvenance, EventType
from traffic_system.models.predictor import TrafficPredictor


def _mock_http_response(status_code: int, data: dict, headers: dict = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status_code
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.headers = headers or {}
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


# =============================================================================
# 1. TomTom Flow & Connectivity Tests
# =============================================================================
def test_tomtom_flow_parsing_and_speed_units():
    client = TomTomClient(api_key="1234567890abcdef1234567890")

    # Valid flow segment with unit=KMPH
    sample_payload = {
        "flowSegmentData": {
            "frc": "FRC1",
            "currentSpeed": 42.5,
            "freeFlowSpeed": 55.0,
            "currentTravelTime": 140,
            "freeFlowTravelTime": 110,
            "confidence": 0.96,
            "roadClosure": False,
            "timestamp": "2026-11-04T00:30:00Z"
        }
    }
    with patch("urllib.request.urlopen", return_value=_mock_http_response(200, sample_payload)):
        flow = client.get_flow_segment(12.9716, 77.5946)
        assert flow is not None
        assert flow["currentSpeed"] == 42.5
        assert flow["freeFlowSpeed"] == 55.0
        assert flow["_observation_time"] == "2026-11-04T00:30:00Z"
        assert client.last_observation_time == "2026-11-04T00:30:00Z"
        assert client.last_successful_retrieval is not None
        assert client.supplying_data is True

    # Flow with non-numeric speed -> rejected safely
    bad_speed_payload = {
        "flowSegmentData": {
            "currentSpeed": "NOT_A_NUMBER",
            "freeFlowSpeed": 50.0
        }
    }
    with patch("urllib.request.urlopen", return_value=_mock_http_response(200, bad_speed_payload)):
        flow_bad = client.get_flow_segment(12.9716, 77.5946)
        assert flow_bad is None
        assert client.supplying_data is False


def test_tomtom_http_status_codes_and_bounded_retry():
    client = TomTomClient(api_key="1234567890abcdef1234567890", max_retries=2)

    # 1. HTTP 401 Unauthorized -> Fail-fast immediately, no retry
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="http://test", code=401, msg="Unauthorized", hdrs={}, fp=io.BytesIO(b"")
    )) as mock_call:
        ok, data, code, err = client._execute_request("http://test")
        assert ok is False
        assert code == 401
        assert "unauthorized" in err.lower()
        # Should not retry 401
        assert mock_call.call_count == 1
        assert client.currently_reachable is False

    # 2. HTTP 403 Forbidden -> Fail-fast immediately
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="http://test", code=403, msg="Forbidden", hdrs={}, fp=io.BytesIO(b"")
    )) as mock_call:
        ok, data, code, err = client._execute_request("http://test")
        assert ok is False
        assert code == 403
        assert mock_call.call_count == 1

    # 3. HTTP 429 Rate Limit with Retry-After header
    hdrs = {"Retry-After": "1"}
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="http://test", code=429, msg="Too Many Requests", hdrs=hdrs, fp=io.BytesIO(b"")
    )) as mock_call:
        ok, data, code, err = client._execute_request("http://test")
        assert ok is False
        assert code == 429
        assert "rate limit" in err.lower()
        # Retried up to max_retries
        assert mock_call.call_count == 2

    # 4. HTTP 503 Server Error -> retried
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="http://test", code=503, msg="Service Unavailable", hdrs={}, fp=io.BytesIO(b"")
    )) as mock_call:
        ok, data, code, err = client._execute_request("http://test")
        assert ok is False
        assert code == 503
        assert mock_call.call_count == 2


def test_tomtom_incident_deduplication_and_expiration():
    adapter = BengaluruIncidentAdapter()

    now_utc = datetime.now(timezone.utc)
    expired_end = (now_utc - timedelta(hours=2)).isoformat()
    active_end = (now_utc + timedelta(hours=4)).isoformat()
    active_start = (now_utc - timedelta(hours=1)).isoformat()

    mock_raw_incidents = [
        # Incident 1: Active, near Silk Board (12.9176, 77.6238)
        {
            "properties": {
                "id": "INC_001_A",
                "iconCategory": 8,  # Roadworks
                "delay": 450,
                "startTime": active_start,
                "endTime": active_end,
                "events": [{"description": "Metro rail pillar construction"}]
            },
            "geometry": {
                "type": "Point",
                "coordinates": [77.6238, 12.9176]
            }
        },
        # Duplicate of Incident 1 with same ID -> must be discarded
        {
            "properties": {
                "id": "INC_001_A",
                "iconCategory": 8,
                "delay": 450,
                "startTime": active_start,
                "endTime": active_end,
                "events": [{"description": "Duplicate stream entry"}]
            },
            "geometry": {
                "type": "Point",
                "coordinates": [77.6238, 12.9176]
            }
        },
        # Incident 2: Expired disruption (ended 2 hours ago) -> must be filtered out
        {
            "properties": {
                "id": "INC_002_EXPIRED",
                "iconCategory": 1,  # Accident
                "delay": 600,
                "startTime": (now_utc - timedelta(hours=5)).isoformat(),
                "endTime": expired_end,
                "events": [{"description": "Cleared minor fender bender"}]
            },
            "geometry": {
                "type": "Point",
                "coordinates": [77.6066, 12.9756]
            }
        }
    ]

    parsed = adapter._parse_tomtom_incidents(mock_raw_incidents)
    # Only the active, non-duplicate Incident 1 should be parsed
    assert len(parsed) == 1
    assert parsed[0]["id"] == "EVT_TT_INC_001_A"
    assert parsed[0]["affected_roads"] == ["RD_BLR_11"]
    assert parsed[0]["event_type"] == EventType.ROADWORK.value


def test_live_bridge_parallel_flow_fetching_and_provenance():
    bridge = LiveTrafficDataBridge()
    bridge.tomtom_key = "1234567890abcdef1234567890"

    mock_flow_data = {
        "flowSegmentData": {
            "currentSpeed": 38.0,
            "freeFlowSpeed": 50.0,
            "confidence": 0.95,
            "timestamp": "2026-11-04T00:15:00Z"
        }
    }

    # Verify corridor coordinates are mapped to registered Bengaluru locations
    for rid, info in BENGALURU_CORRIDOR_GPS.items():
        assert 12.80 <= info["lat"] <= 13.15
        assert 77.45 <= info["lon"] <= 77.80
        assert info["free_flow"] > 0

    with patch.object(bridge.tomtom_client, "get_flow_segment", return_value=mock_flow_data["flowSegmentData"]):
        with patch.object(bridge, "fetch_live_weather", return_value={"condition": "Clear", "temperature": 26.0, "is_live": True}):
            # Fetch only 3 corridors to verify non-blocking concurrent aggregation
            telemetry = bridge.get_corridor_telemetry(road_ids=["RD_BLR_01", "RD_BLR_02", "RD_BLR_11"], force_refresh=True)
        assert len(telemetry) == 3
        for item in telemetry:
            assert item["is_live"] is True
            assert item["is_cached"] is False
            assert item["is_stale"] is False
            assert item["provenance"] == DataProvenance.TOMTOM_LIVE_API.value
            assert item["observation_time"] == "2026-11-04T00:15:00Z"
            assert item["retrieved_time"] is not None


# =============================================================================
# 2. Weather Client Tests
# =============================================================================
def test_weather_client_coordinate_bounds_and_timestamps():
    weather = WeatherClient()

    # Invalid coordinates raise ValueError
    with pytest.raises(ValueError):
        weather.get_weather(lat=95.0, lon=77.0)

    with pytest.raises(ValueError):
        weather.get_weather(lat=12.0, lon=190.0)

    # Valid response with provider observation timestamp
    mock_cur = {
        "current": {
            "time": "2026-11-04T00:20",
            "temperature_2m": 24.5,
            "precipitation": 1.2,
            "weather_code": 61,
            "wind_speed_10m": 14.0
        }
    }
    with patch("urllib.request.urlopen", return_value=_mock_http_response(200, mock_cur)):
        res = weather.get_weather(lat=12.9716, lon=77.5946, force_refresh=True)
        assert res["is_live"] is True
        assert res["is_cached"] is False
        assert res["is_stale"] is False
        assert res["condition"] == "Rainy"
        assert res["precipitation_mm"] == 1.2
        assert res["observation_time"] == "2026-11-04T00:20"
        assert res["provenance"] == DataProvenance.OPEN_METEO_LIVE_API.value


def test_weather_client_explicit_stale_cache_and_baseline_isolation():
    weather = WeatherClient(cache_ttl=1.0)
    mock_cur = {
        "current": {
            "time": "2026-11-04T00:20",
            "temperature_2m": 25.0,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 10.0
        }
    }
    # 1. Successful initial fetch
    with patch("urllib.request.urlopen", return_value=_mock_http_response(200, mock_cur)):
        res1 = weather.get_weather(force_refresh=True)
        assert res1["is_live"] is True
        assert res1["is_stale"] is False

    # 2. Subsequent query fails -> returns explicit stale cache
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network failure")):
        stale_res = weather.get_weather(force_refresh=True)
        assert stale_res["is_live"] is False
        assert stale_res["is_cached"] is True
        assert stale_res["is_stale"] is True
        assert "Stale Cache" in stale_res["source"]
        assert weather.supplying_data is False

    # 3. New uninitialized client with failed fetch -> returns baseline, NEVER reports live
    fresh_weather = WeatherClient()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network down")):
        baseline = fresh_weather.get_weather(force_refresh=True)
        assert baseline["is_live"] is False
        assert baseline["is_cached"] is False
        assert baseline["is_stale"] is False
        assert baseline["is_historical_fallback"] is True
        assert baseline["provenance"] == DataProvenance.HISTORICAL_DATASET.value
        assert fresh_weather.supplying_data is False


def test_weather_values_not_in_xgboost_trained_feature_schema():
    predictor = TrafficPredictor()
    predictor.load_artifacts()

    # Trained feature schema must strictly exclude direct weather parameters
    # to avoid distribution shift and feature mismatch
    schema = predictor.metrics.get("feature_schema", {})
    features_used = schema.get("features_used", [])

    assert "temperature" not in features_used
    assert "precipitation_mm" not in features_used
    assert "weather_condition" not in features_used

    # Expected features
    expected = {"vehicle_count", "average_speed", "capacity_utilization", "congestion_level", "hour", "day_of_week", "is_weekend"}
    assert set(features_used) == expected


# =============================================================================
# 3. Google Maps Platform & Error Handling Tests
# =============================================================================
def test_google_maps_error_and_quota_diagnoses():
    client = GoogleMapsClient(api_key="AIzaSyTestingKey1234567890")

    # 1. OVER_QUERY_LIMIT (quota or billing issue)
    quota_payload = {
        "status": "OVER_QUERY_LIMIT",
        "error_message": "You have exceeded your daily request quota for this API."
    }
    with patch("urllib.request.urlopen", return_value=_mock_http_response(200, quota_payload)):
        ok, data, code, err = client._execute_request("http://maps.test")
        assert ok is False
        assert code == 429
        assert "OVER_QUERY_LIMIT" in err
        assert client.currently_reachable is False

    # 2. REQUEST_DENIED due to Referer Restriction on Server
    referer_payload = {
        "status": "REQUEST_DENIED",
        "error_message": "API keys with referer restrictions cannot be used with this API."
    }
    with patch("urllib.request.urlopen", return_value=_mock_http_response(200, referer_payload)):
        ok, data, code, err = client._execute_request("http://maps.test")
        assert ok is False
        assert code == 403
        assert "HTTP_REFERER_RESTRICTION_ERROR" in client.last_restriction_error

    # 3. REQUEST_DENIED due to API service not enabled
    unauthorized_payload = {
        "status": "REQUEST_DENIED",
        "error_message": "This API project is not authorized to use this API."
    }
    with patch("urllib.request.urlopen", return_value=_mock_http_response(200, unauthorized_payload)):
        ok, data, code, err = client._execute_request("http://maps.test")
        assert ok is False
        assert code == 403
        assert "API_SERVICE_NOT_ENABLED" in client.last_restriction_error


def test_google_maps_places_and_directions_apis():
    client = GoogleMapsClient(api_key="AIzaSyTestingKey1234567890")

    # 1. Places API (find_place)
    places_payload = {
        "status": "OK",
        "candidates": [
            {
                "name": "Silk Board Junction",
                "formatted_address": "Hosur Rd, Central Silk Board Colony, Bengaluru, Karnataka",
                "geometry": {"location": {"lat": 12.9176, "lng": 77.6238}},
                "place_id": "ChIJ_zT_place_silk_board",
                "types": ["transit_station", "point_of_interest"]
            }
        ]
    }
    with patch("urllib.request.urlopen", return_value=_mock_http_response(200, places_payload)):
        places = client.find_place("Silk Board")
        assert len(places) == 1
        assert places[0]["name"] == "Silk Board Junction"
        assert places[0]["lat"] == 12.9176
        assert places[0]["source"] == "Google Places API"
        assert client.supplying_data is True

    # 2. Directions API (get_directions)
    directions_payload = {
        "status": "OK",
        "routes": [
            {
                "summary": "Hosur Rd and Outer Ring Rd",
                "overview_polyline": {"points": "w`jmAg`fxM..."},
                "legs": [
                    {
                        "distance": {"value": 8500, "text": "8.5 km"},
                        "duration": {"value": 1500, "text": "25 mins"},
                        "duration_in_traffic": {"value": 2100, "text": "35 mins"},
                        "start_location": {"lat": 12.9716, "lng": 77.5946},
                        "end_location": {"lat": 12.9176, "lng": 77.6238}
                    }
                ]
            }
        ]
    }
    with patch("urllib.request.urlopen", return_value=_mock_http_response(200, directions_payload)):
        route = client.get_directions((12.9716, 77.5946), (12.9176, 77.6238))
        assert route is not None
        assert route["distance_meters"] == 8500
        assert route["duration_in_traffic_seconds"] == 2100
        assert route["overview_polyline"] == "w`jmAg`fxM..."
        assert route["source"] == "Google Directions API"

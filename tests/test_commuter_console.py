"""
tests/test_commuter_console.py - Unit & Integration Tests for Commuter / Road User Console
Verifies:
1. TomTom Calculate Route method & parsing
2. Live Traffic Data Bridge route evaluation & shared cache TTL
3. Graceful fallback on unavailable TomTom response without fake live labeling
4. Standard Operations RouteNavigator date/time horizon filtering & travel-time comparison
5. Municipal event audit integrity (source name, canonical URL, verification date, status)
6. Exclusion of unverified seed events from official commuter views
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.live.bridge import LiveTrafficDataBridge, get_live_bridge
from traffic_system.events.event_manager import EventManager
from traffic_system.routing.navigator import RouteNavigator
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.core.entities import RouteEvaluation, DataProvenance


class TestTomTomCalculateRoute:
    def test_calculate_route_mock_success(self):
        client = TomTomClient(api_key="mock_key_123456789012")

        mock_payload = {
            "routes": [
                {
                    "summary": {
                        "lengthInMeters": 9250,
                        "travelTimeInSeconds": 1380,
                        "trafficDelayInSeconds": 240,
                        "departureTime": "2026-11-04T14:00:00+05:30",
                        "arrivalTime": "2026-11-04T14:23:00+05:30"
                    },
                    "legs": [
                        {
                            "points": [
                                {"latitude": 12.9784, "longitude": 77.6408},
                                {"latitude": 12.9750, "longitude": 77.6300},
                                {"latitude": 12.9176, "longitude": 77.6238}
                            ]
                        }
                    ]
                },
                {
                    "summary": {
                        "lengthInMeters": 11200,
                        "travelTimeInSeconds": 1560,
                        "trafficDelayInSeconds": 60
                    },
                    "legs": [
                        {
                            "points": [
                                {"latitude": 12.9784, "longitude": 77.6408},
                                {"latitude": 12.9176, "longitude": 77.6238}
                            ]
                        }
                    ]
                }
            ]
        }

        with patch.object(client, "_execute_request", return_value=(True, mock_payload, 200, "")):
            res = client.calculate_route(12.9784, 77.6408, 12.9176, 77.6238)

            assert res is not None
            assert res["status"] == "LIVE_CALCULATED"
            assert res["travel_time_minutes"] == 23.0
            assert res["traffic_delay_minutes"] == 4.0
            assert res["length_meters"] == 9250
            assert len(res["points"]) == 3
            assert len(res["alternatives"]) == 1
            assert res["alternatives"][0]["travel_time_minutes"] == 26.0

    def test_calculate_route_failure_handling(self):
        client = TomTomClient(api_key="mock_key_123456789012")

        with patch.object(client, "_execute_request", return_value=(False, None, 401, "Invalid API key")):
            res = client.calculate_route(12.9784, 77.6408, 12.9176, 77.6238)
            assert res is None


class TestLiveTrafficBridgeRouting:
    @pytest.fixture
    def bridge(self):
        b = get_live_bridge()
        b.clear_cache()
        orig_fetch = b.fetch_live_weather
        # Mock weather to avoid unmocked external Open-Meteo network calls in unit tests
        mock_weather = {
            "condition": "Clear",
            "temperature": 27.5,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 10.5,
            "weather_code": 1,
            "source": "Mock Weather Baseline",
            "is_live": False,
            "is_cached": False,
            "is_stale": False,
            "is_historical_fallback": True,
            "provenance": "Historical dataset",
            "observation_time": "2026-11-04T08:00:00+00:00",
            "request_time": "2026-11-04T08:00:00+00:00",
            "retrieved_time": "2026-11-04T08:00:00+00:00"
        }
        b.fetch_live_weather = MagicMock(return_value=mock_weather)
        yield b
        b.fetch_live_weather = orig_fetch

    def test_evaluate_live_route_fallback_when_tomtom_unreachable(self, bridge):
        with patch.object(bridge.tomtom_client, "calculate_route", return_value=None):
            res = bridge.evaluate_live_route("RD_BLR_01", "RD_BLR_11")

            assert res["status"] == "FALLBACK_TOPOLOGICAL"
            assert res["is_live"] is False
            assert res["is_fallback"] is True
            assert "fallback_reason" in res
            assert res["provider"] == "Empirical Bengaluru Topology (Fallback)"
            assert res["travel_time_minutes"] > 0
            assert "primary_route" in res
            assert "recommended_route" in res

    def test_evaluate_live_route_caching(self, bridge):
        bridge.clear_cache()
        with patch.object(bridge.tomtom_client, "calculate_route", return_value=None):
            r1 = bridge.evaluate_live_route("RD_BLR_01", "RD_BLR_06")
            assert r1.get("is_cached") is False

            r2 = bridge.evaluate_live_route("RD_BLR_01", "RD_BLR_06")
            assert r2.get("is_cached") is True

    def test_corridor_telemetry_observation_tracking(self, bridge):
        corridors = bridge.get_corridor_telemetry()
        assert len(corridors) == 24
        for c in corridors:
            assert "has_valid_live_observation" in c
            assert "vehicle_count_source" in c
            assert c["vehicle_count_source"] == "Topological Baseline Calibration"
            assert "observation_time" in c
            assert "retrieved_time" in c


class TestStandardOperationsRouteNavigator:
    @pytest.fixture
    def navigator(self):
        p = TrafficPredictor()
        p.load_artifacts()
        em = EventManager()
        return RouteNavigator(predictor=p, event_manager=em)

    def test_evaluate_route_future_date_provenance(self, navigator):
        eval_res = navigator.evaluate_route("RD_BLR_01", "RD_BLR_06", "2026-11-20", "18:30")

        assert isinstance(eval_res, RouteEvaluation)
        assert eval_res.departure_date == "2026-11-20"
        assert eval_res.departure_time == "18:30"
        assert eval_res.is_historical_model_estimate is True
        assert eval_res.primary_travel_time_minutes > 0
        assert eval_res.recommended_travel_time_minutes > 0
        assert "estimates based on topological network models" in eval_res.disclaimer


class TestEventDataIntegrity:
    def test_all_published_events_have_required_audit_fields(self):
        em = EventManager()
        published = em.get_scheduled_events(published_only=True)

        assert len(published) > 0
        for evt in published:
            assert "source_name" in evt and evt["source_name"], f"Missing source_name in {evt['id']}"
            assert "source_url" in evt and evt["source_url"].startswith("http"), f"Invalid source_url in {evt['id']}"
            assert "publication_date" in evt and evt["publication_date"], f"Missing publication_date in {evt['id']}"
            assert "verification_date" in evt and evt["verification_date"], f"Missing verification_date in {evt['id']}"
            assert "affected_roads" in evt and len(evt["affected_roads"]) > 0
            assert evt.get("verification_status") == "OFFICIAL_VERIFIED"

    def test_unverified_seed_events_are_not_published_as_official(self):
        em = EventManager()
        all_evts = em.get_all_events()

        seed = next((e for e in all_evts if e["id"] == "EVT_001"), None)
        assert seed is not None
        assert seed.get("is_published") is False
        assert seed.get("verification_status") == "UNVERIFIED_PENDING"

        # Verify excluded from commuter published feed
        commuter_evts = em.get_scheduled_events(published_only=True)
        assert not any(e["id"] == "EVT_001" for e in commuter_evts)


class TestCommuterConsoleE2EWorkflow:
    """
    End-to-end integration test of the Road User console workflow covering:
    - Section 1: Standard Operations (origin/dest, future date/time, historical disclaimer, verified events)
    - Section 2: Live Traffic (TomTom route calculation, live telemetry, and explicit fallback)
    - Section 3: Traffic Heat Map (all 24 registered corridors, flyout data source, unavailable state)
    """

    def test_section_1_standard_operations_future_journey_planning(self):
        p = TrafficPredictor()
        p.load_artifacts()
        em = EventManager()
        nav = RouteNavigator(predictor=p, event_manager=em)

        eval_res = nav.evaluate_route(
            origin_road="RD_BLR_01",
            destination_road="RD_BLR_06",
            departure_date="2026-11-15",
            departure_time="09:30"
        )

        assert eval_res.departure_date == "2026-11-15"
        assert eval_res.departure_time == "09:30"
        assert eval_res.is_historical_model_estimate is True
        assert "estimates based on topological network models" in eval_res.disclaimer
        assert eval_res.primary_travel_time_minutes > 0
        assert eval_res.recommended_travel_time_minutes > 0
        # If route has active municipal events, verify their integrity
        for evt in eval_res.active_events:
            assert evt["verification_status"] == "OFFICIAL_VERIFIED"
            assert evt["source_name"]
            assert evt["source_url"].startswith("http")

    def test_section_2_live_traffic_live_and_fallback_routes(self):
        bridge = get_live_bridge()
        bridge.clear_cache()
        mock_weather = {
            "condition": "Clear", "temperature": 26.0,
            "precipitation_mm": 0.0, "wind_speed_kmh": 12.0, "weather_code": 1,
            "source": "Mock Baseline", "is_live": False, "is_cached": False,
            "is_stale": False, "is_historical_fallback": True, "provenance": "Mock Baseline",
            "observation_time": "2026-11-04T08:00:00+00:00",
            "request_time": "2026-11-04T08:00:00+00:00", "retrieved_time": "2026-11-04T08:00:00+00:00"
        }

        # Test Successful TomTom Calculate Route response
        mock_tomtom_payload = {
            "status": "LIVE_CALCULATED",
            "travel_time_minutes": 18.5,
            "travel_time_seconds": 1110,
            "traffic_delay_minutes": 3.2,
            "traffic_delay_seconds": 192,
            "length_meters": 7800,
            "departure_time": "2026-11-04T14:30:00+05:30",
            "arrival_time": "2026-11-04T14:48:30+05:30",
            "observation_time": "2026-11-04T14:30:00+05:30",
            "retrieved_time": "2026-11-04T14:30:00+05:30",
            "points": [[12.9784, 77.6408], [12.9756, 77.6066]],
            "alternatives": []
        }

        with patch.object(bridge, "fetch_live_weather", return_value=mock_weather), \
             patch.object(bridge, "is_live_key_configured", return_value=True), \
             patch.object(bridge.tomtom_client, "calculate_route", return_value=mock_tomtom_payload):
            live_res = bridge.evaluate_live_route("RD_BLR_01", "RD_BLR_02")
            assert live_res["status"] == "LIVE_ROUTE_SUCCESS"
            assert live_res["is_live"] is True
            assert live_res["is_fallback"] is False
            assert live_res["travel_time_minutes"] == 18.5
            assert live_res["traffic_delay_minutes"] == 3.2
            assert live_res["provider"] == "TomTom Calculate Route API"

        # Test Explicit Fallback when TomTom fails
        bridge.clear_cache()
        with patch.object(bridge, "fetch_live_weather", return_value=mock_weather), \
             patch.object(bridge, "is_live_key_configured", return_value=False), \
             patch.object(bridge.tomtom_client, "calculate_route", return_value=None):
            fallback_res = bridge.evaluate_live_route("RD_BLR_01", "RD_BLR_02")
            assert fallback_res["status"] == "FALLBACK_TOPOLOGICAL"
            assert fallback_res["is_live"] is False
            assert fallback_res["is_fallback"] is True
            assert "fallback_reason" in fallback_res
            assert fallback_res["provider"] == "Empirical Bengaluru Topology (Fallback)"
            assert fallback_res["travel_time_minutes"] > 0

    def test_section_3_heatmap_all_24_corridors_and_observation_tracking(self):
        bridge = get_live_bridge()
        corridors = bridge.get_corridor_telemetry()

        # Must strictly cover all 24 registered Bengaluru corridors
        assert len(corridors) == 24
        corridor_ids = {c["road_id"] for c in corridors}
        for i in range(1, 25):
            expected_id = f"RD_BLR_{i:02d}"
            assert expected_id in corridor_ids

        # Corridor telemetry schema check
        for c in corridors:
            assert "current_speed" in c
            assert "free_flow_speed" in c
            assert "congestion_level" in c
            assert "has_valid_live_observation" in c
            assert "provenance" in c
            assert "observation_time" in c
            assert "vehicle_count_source" in c
            # Verify vehicle counts are NOT fabricated from TomTom speed data
            assert c["vehicle_count_source"] == "Topological Baseline Calibration"


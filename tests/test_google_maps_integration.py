"""
tests/test_google_maps_integration.py - Google Maps & Lane-Routing Unit & Integration Tests
Validates Google Maps Platform integration, place recognition fuzzy matching,
multi-lane corridor intelligence, route polyline geometry, and macroscopic heatmap telemetry.
"""

import pytest
from unittest.mock import patch, MagicMock
from traffic_system.integrations.google_maps_client import GoogleMapsClient
from traffic_system.integrations.api_manager import get_api_manager
from traffic_system.core.road_registry import (
    ROAD_REGISTRY,
    CORRIDOR_GEO_REGISTRY,
    get_corridor_lane_info,
    get_corridor_coordinates,
    match_places_to_corridors
)
from traffic_system.live.bridge import get_live_bridge
from traffic_system.routing.navigator import RouteNavigator
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager


def test_google_maps_client_masking_and_configuration():
    client = GoogleMapsClient(api_key="")
    assert not client.is_configured()
    assert client.get_masked_key() == ""

    client.set_api_key("AIzaSyFakeKeyForTesting1234567")
    assert client.is_configured()
    assert client.get_masked_key().startswith("****")
    assert client.get_masked_key() == "****4567"
    assert "AIzaSy" not in client.get_masked_key()

    # Test status payload
    status = client.get_status()
    assert status["configured"] is True
    assert status["masked_key"] == "****4567"
    assert "base_url" in status


def test_google_maps_api_manager_integration():
    api_mgr = get_api_manager()
    providers = api_mgr.get_providers()["providers"]
    gm_provider = next((p for p in providers if p["name"] == "Google Maps Platform"), None)
    assert gm_provider is not None
    assert gm_provider["type"] == "places_geocoding_and_heatmap"

    # Test updating config
    ok, msg, data = api_mgr.update_google_maps_config("AIzaSyTestingKey9988")
    assert ok is True
    assert data["configured"] is True
    assert data["masked_key"] == "****9988"

    # Test connection call handles unauthenticated gracefully
    with patch.object(api_mgr.google_maps, "test_connection", return_value=(False, "The provided API key is invalid.", 25.0)):
        reachable, test_msg, test_data = api_mgr.test_google_maps()
        assert "message" in test_data
        assert "latency_ms" in test_data


def test_place_recognition_fuzzy_matching():
    # 1. Match Indiranagar
    matches = match_places_to_corridors("Indiranagar", limit=5)
    assert len(matches) > 0
    road_ids = [m["road_id"] for m in matches]
    assert "RD_BLR_01" in road_ids or "RD_BLR_04" in road_ids or "RD_BLR_17" in road_ids
    assert all("coordinates" in m and len(m["coordinates"]) > 0 for m in matches)
    assert all("lanes" in m and m["lanes"] >= 2 for m in matches)

    # 2. Match Silk Board
    silk_matches = match_places_to_corridors("Silk Board", limit=3)
    assert len(silk_matches) > 0
    assert silk_matches[0]["road_id"] == "RD_BLR_11"

    # 3. Match Hebbal Flyover
    hebbal_matches = match_places_to_corridors("Hebbal", limit=3)
    assert len(hebbal_matches) > 0
    hebbal_ids = [m["road_id"] for m in hebbal_matches]
    assert "RD_BLR_05" in hebbal_ids or "RD_BLR_03" in hebbal_ids

    # 4. Empty query defaults to top transit hubs
    default_matches = match_places_to_corridors("", limit=5)
    assert len(default_matches) == 5


def test_corridor_lane_intelligence_and_geometry():
    for r_id in ROAD_REGISTRY:
        lane_info = get_corridor_lane_info(r_id)
        assert lane_info["lanes"] in (4, 6, 8), f"{r_id} lanes={lane_info['lanes']} unexpected"
        assert len(lane_info["lane_breakdown"]) >= 2
        assert lane_info["speed_limit_kmh"] >= 40.0
        coords = get_corridor_coordinates(r_id)
        assert len(coords) >= 2, f"{r_id} coordinates missing"
        # Coordinates must be valid Bengaluru lat/lon
        for lat, lon in coords:
            assert 12.80 <= lat <= 13.15, f"{r_id} lat {lat} out of range"
            assert 77.45 <= lon <= 77.80, f"{r_id} lon {lon} out of range"


def test_route_navigator_lane_guidance_and_polylines():
    predictor = TrafficPredictor()
    predictor.load_artifacts()
    event_mgr = EventManager()
    navigator = RouteNavigator(predictor, event_mgr)

    evaluation = navigator.evaluate_route("RD_BLR_01", "RD_BLR_04", "2026-11-03", "10:00")
    eval_dict = evaluation.to_dict()

    assert len(eval_dict["primary_route"]) >= 2
    assert "primary_lane_guidance" in eval_dict
    assert "recommended_lane_guidance" in eval_dict
    assert "primary_polylines" in eval_dict
    assert "recommended_polylines" in eval_dict
    assert len(eval_dict["primary_lane_guidance"]) == len(eval_dict["primary_route"])
    assert len(eval_dict["primary_polylines"]) > 0

    first_lane = eval_dict["primary_lane_guidance"][0]
    assert "lanes" in first_lane
    assert "recommended_lane" in first_lane
    assert "speed_kmh" in first_lane


def test_heatmap_telemetry_greenshields_weights():
    bridge = get_live_bridge()
    # Controlled telemetry fixtures for all 24 corridors: avoids external live weather or network requests
    fixture_telemetry = []
    levels = ["Low", "Moderate", "High", "Severe"]
    for i, (r_id, meta) in enumerate(ROAD_REGISTRY.items()):
        spd = 25.0 + (i % 25)
        vol = 20000 + i * 1500
        fixture_telemetry.append({
            "road_id": r_id,
            "road_name": meta.get("bangalore_name", r_id),
            "current_speed": spd,
            "free_flow_speed": 50.0,
            "vehicle_count": vol,
            "capacity_utilization": min(95.0, 30.0 + (i * 2.5)),
            "congestion_level": levels[i % len(levels)],
            "is_live": False,
            "provenance": "Controlled Fixture"
        })

    with patch.object(bridge, "get_corridor_telemetry", return_value=fixture_telemetry):
        heatmap = bridge.get_heatmap_telemetry()

    assert heatmap["status"] == "success"
    assert heatmap["point_count"] >= 24
    assert len(heatmap["points"]) == heatmap["point_count"]

    for pt in heatmap["points"]:
        assert "lat" in pt and "lng" in pt
        assert 0.1 <= pt["weight"] <= 1.0, f"Weight {pt['weight']} out of normalized bounds"
        assert pt["density_k"] > 0.0
        assert pt["congestion"] in ("Low", "Moderate", "High", "Severe")
        assert "road_name" in pt
        assert pt["speed_kmh"] > 0.0


def test_api_map_config_dual_console_automatic_key_delivery():
    """
    Verifies /api/map/config endpoint delivers browser-usable configuration
    to both Road User and Traffic Management sessions without requiring manual key entry.
    """
    import os
    from app.server import TrafficAppServer

    # Simulate configured environment key
    test_key = "AIzaSyDUMMYTESTKEYFORBROWSER123456"
    orig_env = os.environ.get("GOOGLE_MAPS_API_KEY")
    orig_browser = os.environ.get("GOOGLE_MAPS_BROWSER_KEY")
    try:
        os.environ["GOOGLE_MAPS_API_KEY"] = test_key
        os.environ["GOOGLE_MAPS_BROWSER_KEY"] = test_key
        api_mgr = get_api_manager()
        api_mgr.google_maps.set_api_key(test_key)

        # Mock request to /api/map/config
        server = TrafficAppServer.__new__(TrafficAppServer)
        server.path = "/api/map/config"
        server.headers = {}
        sent_status = []
        sent_body = []
        server.send_response = lambda code, msg=None: sent_status.append(code)
        server.send_header = lambda k, v: None
        server.end_headers = lambda: None
        import io, json
        server.wfile = io.BytesIO()

        server.do_GET()

        assert len(sent_status) > 0 and sent_status[0] == 200
        response_json = json.loads(server.wfile.getvalue().decode("utf-8"))
        assert response_json["success"] is True
        assert response_json["configured"] is True
        assert response_json["api_key"] == test_key
        assert response_json["masked_key"] == "****3456"
        assert response_json["default_center"] == {"lat": 12.9716, "lng": 77.5946}
        assert response_json["default_zoom"] == 12
        assert "places" in response_json["libraries"]
        assert "visualization" in response_json["libraries"]
        assert "geometry" in response_json["libraries"]
    finally:
        if orig_env is not None:
            os.environ["GOOGLE_MAPS_API_KEY"] = orig_env
            get_api_manager().google_maps.set_api_key(orig_env)
        else:
            os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            get_api_manager().google_maps.set_api_key("")
        if orig_browser is not None:
            os.environ["GOOGLE_MAPS_BROWSER_KEY"] = orig_browser
        else:
            os.environ.pop("GOOGLE_MAPS_BROWSER_KEY", None)


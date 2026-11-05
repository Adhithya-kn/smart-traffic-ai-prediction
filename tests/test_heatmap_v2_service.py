"""
tests/test_heatmap_v2_service.py - Unit and Integration Tests for Tri-Pillar Heatmap Engine
Tests /api/map/heatmap/v2 multi-channel telemetry, horizon transition, and physically clamped density.
"""

import pytest
from traffic_system.live.heatmap_service import HeatmapService
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager
from traffic_system.junction.junction_service import JunctionService


def test_heatmap_v2_tri_pillar_payload():
    pred = TrafficPredictor()
    pred.load_artifacts()
    ev_mgr = EventManager()
    jnc_svc = JunctionService(pred, ev_mgr)
    svc = HeatmapService(pred, jnc_svc, ev_mgr)

    # Test complete multi-channel payload at horizon=60m
    data = svc.get_tri_pillar_heatmap(horizon_minutes=60, channel="all")
    assert data["status"] == "success"
    assert data["horizon_minutes"] == 60
    assert "traffic_layer" in data
    assert "crowd_layer" in data
    assert "junction_layer" in data
    assert len(data["traffic_layer"]) >= 24
    assert len(data["junction_layer"]) >= 24
    assert len(data["crowd_layer"]) >= 6

    # Verify physical density bounds on traffic segments
    for corridor in data["traffic_layer"]:
        assert "road_id" in corridor
        assert "sub_segments" in corridor
        for pt in corridor["sub_segments"]:
            assert 0.0 <= pt["weight"] <= 1.0
            assert pt["density_k"] <= 150.0  # Physical jam density clamp (IRC:SP:41 standard)
            assert pt["predicted_los"] in ["Low", "Moderate", "High", "Severe"]
            assert "prob_dist" in pt
            assert len(pt["prob_dist"]) == 4

    # Verify junction Webster metrics
    silk_board = next((j for j in data["junction_layer"] if j["junction_id"] == "INT_BLR_11"), data["junction_layer"][0])
    assert silk_board["queue_meters"] > 0
    assert silk_board["control_delay_sec"] > 0
    assert silk_board["webster_cycle_sec"] >= 45.0
    assert silk_board["green_split_ns_sec"] > 0

    # Verify crowd metrics and Fruin LOS
    majestic = next((c for c in data["crowd_layer"] if "Majestic" in c["name"]), data["crowd_layer"][0])
    assert majestic["ped_density_sqm"] > 0
    assert majestic["fruin_los"].startswith("LOS")
    assert 0.0 <= majestic["vru_conflict_index"] <= 1.0


def test_heatmap_v2_horizon_transition():
    pred = TrafficPredictor()
    pred.load_artifacts()
    ev_mgr = EventManager()
    jnc_svc = JunctionService(pred, ev_mgr)
    svc = HeatmapService(pred, jnc_svc, ev_mgr)

    t0_data = svc.get_tri_pillar_heatmap(horizon_minutes=0, channel="traffic")
    t60_data = svc.get_tri_pillar_heatmap(horizon_minutes=60, channel="traffic")
    assert t0_data["horizon_minutes"] == 0
    assert t60_data["horizon_minutes"] == 60

    # Ensure intermediate horizon is supported
    t30_data = svc.get_tri_pillar_heatmap(horizon_minutes=30, channel="traffic")
    assert t30_data["horizon_minutes"] == 30


def test_server_routes_heatmap_v2_and_legacy_endpoints():
    from app.server import TrafficAppServer
    import io
    import json

    TrafficAppServer.ensure_initialized()

    def make_server(path):
        server = TrafficAppServer.__new__(TrafficAppServer)
        server.command = "GET"
        server.path = path
        server.requestline = f"GET {path} HTTP/1.1"
        server.headers = {}
        server.rfile = io.BytesIO(b"")
        
        class MockWFile:
            def __init__(self):
                self.data = b""
            def write(self, b):
                self.data += b

        server.wfile = MockWFile()
        server._headers_buffer = []
        server.response_code = 200
        server.send_response = lambda code, msg=None: setattr(server, "response_code", code)
        server.send_header = lambda k, v: server._headers_buffer.append((k, v))
        server.end_headers = lambda: None
        return server

    server = make_server("/api/map/heatmap/v2?horizon=15&channel=all")
    server.do_GET()

    # Extract JSON body from response
    payload = json.loads(server.wfile.data.decode("utf-8"))
    assert payload["status"] == "success"
    assert payload["horizon_minutes"] == 15
    assert "traffic_layer" in payload
    assert "crowd_layer" in payload
    assert "junction_layer" in payload

    # Test legacy delegate endpoint
    server2 = make_server("/api/map/heatmap")
    server2.do_GET()

    legacy_payload = json.loads(server2.wfile.data.decode("utf-8"))
    assert legacy_payload["status"] == "success"
    assert "points" in legacy_payload
    assert len(legacy_payload["points"]) > 0
    # Clamped density check
    for pt in legacy_payload["points"]:
        assert pt["density_k"] <= 150.0


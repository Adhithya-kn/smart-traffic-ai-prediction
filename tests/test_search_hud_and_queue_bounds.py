"""
tests/test_search_hud_and_queue_bounds.py - Verification for:
1. Fuzzy place recognition for "Electronic City Expressway"
2. Physical queue length upper bound (<= 450m) across all 24 registered junctions
3. Layout order: Map monitor card placed first in /predict view
4. Tactical HUD VRU LOS parsing and Corridor HUD sync functions
"""

from pathlib import Path
from traffic_system.core.road_registry import match_places_to_corridors, ROAD_REGISTRY
from traffic_system.simulation.signal_optimizer import WebsterSignalOptimizer
from traffic_system.junction.junction_service import JunctionService
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager
from traffic_system.live.heatmap_service import HeatmapService


def test_fuzzy_search_matches_electronic_city_expressway():
    matches = match_places_to_corridors("Electronic City Expressway", limit=5)
    assert len(matches) > 0
    matched_ids = [m["road_id"] for m in matches]
    assert any(rid in ["RD_BLR_06", "RD_BLR_20"] for rid in matched_ids)
    assert matches[0]["score"] >= 80


def test_junction_queue_lengths_physically_bounded():
    pred = TrafficPredictor()
    pred.load_artifacts()
    ev = EventManager()
    jnc = JunctionService(pred, ev)

    for r_id in ROAD_REGISTRY:
        tel = jnc.get_junction_telemetry(road_id=r_id, hour=17, minute=30)
        approaches = tel.get("approaches", [])
        assert len(approaches) > 0
        for app in approaches:
            q_m = app.get("queue_length_meters", 0.0)
            q_v = app.get("queue_vehicles", 0.0)
            assert q_m <= 450.0, f"Junction {r_id} queue exceeded physical link limit: {q_m}m"
            assert q_v <= 65.0, f"Junction {r_id} queue vehicles exceeded link capacity: {q_v}"


def test_heatmap_service_junction_layer_bounded():
    pred = TrafficPredictor()
    pred.load_artifacts()
    ev = EventManager()
    jnc = JunctionService(pred, ev)
    svc = HeatmapService(pred, jnc, ev)

    data = svc.get_tri_pillar_heatmap(horizon_minutes=30, channel="junctions")
    for node in data.get("junction_layer", []):
        assert node["queue_meters"] <= 450.0, f"Queue {node['name']} was {node['queue_meters']}m"
        assert node["queue_vehicles"] <= 65.0


def test_layout_order_map_card_first():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    map_idx = html.find('id="liveMapMonitorCard"')
    forecast_idx = html.find('id="predictForecastCard"')
    assert map_idx != -1 and forecast_idx != -1
    assert map_idx < forecast_idx, "liveMapMonitorCard should precede predictForecastCard in DOM"


def test_app_js_has_corridor_hud_and_vru_fix():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "updateMapLaneHudForCorridor" in js
    assert "highlightMapCorridorPolyline" in js
    assert "LOS\\s+[A-F]" in js or "match(/LOS" in js

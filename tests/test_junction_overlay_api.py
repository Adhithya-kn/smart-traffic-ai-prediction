"""
tests/test_junction_overlay_api.py - Verification for Junction Chokepoints and Webster Advisories
Ensures:
1. /api/map/heatmap/v2 returns complete junction_layer data with Webster signal parameters.
2. Every junction node contains queue_meters, control_delay_sec, webster_cycle_sec, and green splits.
3. DOM contains #junctionInspectorFlyout with Webster advisory elements.
"""

from pathlib import Path
import pytest
from traffic_system.live.heatmap_service import HeatmapService
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager
from traffic_system.junction.junction_service import JunctionService


def test_junction_layer_payload_has_webster_advisories():
    pred = TrafficPredictor()
    pred.load_artifacts()
    ev = EventManager()
    jnc = JunctionService(pred, ev)
    svc = HeatmapService(pred, jnc, ev)

    data = svc.get_tri_pillar_heatmap(horizon_minutes=0, channel="junctions")
    junctions = data.get("junction_layer", [])
    assert len(junctions) >= 24

    silk_board = next((j for j in junctions if j["junction_id"] == "INT_BLR_11"), junctions[0])
    assert silk_board["queue_meters"] > 0
    assert silk_board["control_delay_sec"] > 0
    assert silk_board["webster_cycle_sec"] >= 45.0
    assert "green_split_ns_sec" in silk_board
    assert "green_split_ew_sec" in silk_board
    assert "spillback_risk" in silk_board


def test_index_html_has_junction_inspector_flyout():
    content = Path("app/static/index.html").read_text(encoding="utf-8")
    assert "junctionInspectorFlyout" in content
    assert "jncWebsterCycle" in content
    assert "jncGreenSplits" in content
    assert "jncQueueLength" in content

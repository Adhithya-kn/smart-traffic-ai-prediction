"""
tests/test_junction.py - Test Junction Machine Sight & Intersection Telemetry Engine
"""

from traffic_system.junction.junction_service import JunctionService
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager

def test_junction_service_telemetry():
    pred = TrafficPredictor()
    ev = EventManager()
    js = JunctionService(pred, ev)

    # Test peak hour telemetry with bypass routing
    telem = js.get_junction_telemetry(
        road_id="RD_BLR_01",
        hour=17,
        minute=0,
        is_rerouted=True,
        alternate_road_id="RD_BLR_04",
        date_str="2026-03-18"
    )

    assert telem["road_id"] == "RD_BLR_01"
    assert telem["intersection_id"] == "INT_BLR_05"
    assert telem["is_rerouted"] is True
    assert telem["bypass_corridor"] == "RD_BLR_04"
    assert telem["junction_mode"] == "BYPASS_DIVERSION"
    assert telem["intent_split"]["bypass_turn_pct"] > 50
    assert telem["signals"]["cycle_seconds"] >= 45
    assert len(telem["tracked_vehicles"]) >= 5
    assert telem["primary_vehicle"]["id"] == "CAR 47"
    assert telem["primary_vehicle"]["is_diverted"] is True
    # Ensure active event is recognized
    assert telem["event_impact"]["has_event"] is True

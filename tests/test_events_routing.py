"""
tests/test_events_routing.py - Test Suite for Event Manager & Route Alteration Engine
"""

import pytest
from traffic_system.events.event_manager import EventManager
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.routing.navigator import RouteNavigator

def test_events_and_route_alteration():
    evt_mgr = EventManager()
    events = evt_mgr.get_all_events()
    assert len(events) >= 5, "Baseline events should be seeded"

    predictor = TrafficPredictor()
    predictor.load_artifacts()
    navigator = RouteNavigator(predictor, evt_mgr)

    # 1. Test evaluation during an active event on RD_BLR_01 (100 Feet Road on calibrated presentation date 2026-04-30)
    eval_res = navigator.evaluate_route("RD_BLR_01", "RD_BLR_04", "2026-04-30", "17:00")
    assert eval_res.primary_congestion in ["High", "Severe"], "Primary route should detect severe bottleneck"
    assert eval_res.is_rerouted is True, "System must trigger altered bypass route"
    assert eval_res.time_saved_minutes > 0, "Altered route must save travel time"
    assert len(eval_res.recommended_route) > 0, "Altered route must have road segments"
    assert len(eval_res.active_events) > 0, "Active event must be detected"

    # Also verify backward compatibility with 2026-03-18
    eval_res_prev = navigator.evaluate_route("RD_BLR_01", "RD_BLR_04", "2026-03-18", "17:00")
    assert eval_res_prev.is_rerouted is True

    # 2. Test evaluation during off-peak hours with no events
    eval_clear = navigator.evaluate_route("RD_BLR_03", "RD_BLR_05", "2026-04-30", "03:00")
    assert eval_clear.primary_congestion in ["Low", "Moderate"], "Off-peak route should have low congestion"

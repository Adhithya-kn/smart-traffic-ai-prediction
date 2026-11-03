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

    initial_pub = evt_mgr.get_scheduled_events(published_only=True)
    evt_mgr.unpublish_event("EVT_001")

    predictor = TrafficPredictor()
    predictor.load_artifacts()
    navigator = RouteNavigator(predictor, evt_mgr)

    eval_pre = navigator.evaluate_route("RD_BLR_01", "RD_BLR_04", "2026-04-30", "17:00")
    assert len(eval_pre.active_events) == 0, "Unpublished event must not affect road users"

    ok, msg, published_evt = evt_mgr.publish_event("EVT_001")
    assert ok is True, f"Publishing failed: {msg}"
    assert published_evt["is_published"] is True
    alert = evt_mgr.get_latest_alert()
    assert alert is not None
    assert alert["id"] == "EVT_001"
    assert "Early Warning" in alert["headline"]

    eval_res = navigator.evaluate_route("RD_BLR_01", "RD_BLR_04", "2026-04-30", "17:00")
    assert eval_res.primary_congestion in ["High", "Severe"], "Primary route should detect severe bottleneck"
    assert eval_res.is_rerouted is True, "System must trigger altered bypass route"
    assert eval_res.time_saved_minutes > 0, "Altered route must save travel time"
    assert len(eval_res.recommended_route) > 0, "Altered route must have road segments"
    assert len(eval_res.active_events) > 0, "Active event must be detected"

    eval_res_prev = navigator.evaluate_route("RD_BLR_01", "RD_BLR_04", "2026-03-18", "17:00")
    assert eval_res_prev.is_rerouted is True

    unpub_ok, unpub_msg = evt_mgr.unpublish_event("EVT_001")
    assert unpub_ok is True
    assert evt_mgr.get_latest_alert()["action"] == "RETRACTED"

    eval_clear = navigator.evaluate_route("RD_BLR_03", "RD_BLR_05", "2026-04-30", "03:00")
    assert eval_clear.primary_congestion in ["Low", "Moderate"], "Off-peak route should have low congestion"

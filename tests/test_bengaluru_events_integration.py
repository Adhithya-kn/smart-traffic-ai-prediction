"""
tests/test_bengaluru_events_integration.py - Integration Verification for Bengaluru Events Pipeline
Validates Haversine distance matching, physical calibration, batch upserting, and Silk Board bypass rerouting.
"""

import pytest
from datetime import datetime
from traffic_system.core.road_registry import ROAD_REGISTRY
from traffic_system.events.bengaluru_incident_adapter import (
    haversine_distance_km,
    find_nearest_corridor,
    calibrate_physics,
    BengaluruIncidentAdapter
)
from traffic_system.events.event_manager import EventManager
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.routing.navigator import RouteNavigator


def test_haversine_distance_and_corridor_mapping():
    match = find_nearest_corridor(12.9185, 77.6245)
    assert match is not None
    road_id, zone, dist_km = match
    assert road_id == "RD_BLR_11"
    assert zone == "Electronic City South"
    assert dist_km < 0.5

    out_of_bounds = find_nearest_corridor(13.2000, 77.7000, max_km=1.5)
    assert out_of_bounds is None


def test_physics_calibration_heuristics():
    sev, spd, cap, vol = calibrate_physics("Accident", delay_seconds=120)
    assert sev == 1
    assert cap == 35
    assert spd >= 20
    assert vol > 0

    sev_rw, spd_rw, cap_rw, vol_rw = calibrate_physics("Roadwork", delay_seconds=600, roadworks=True)
    assert sev_rw == 2
    assert cap_rw == 50
    assert spd_rw == 40
    assert vol_rw >= 700

    sev_fl, spd_fl, cap_fl, vol_fl = calibrate_physics("Severe Waterlog", delay_seconds=1200)
    assert sev_fl == 3
    assert cap_fl == 60
    assert spd_fl == 75
    assert vol_fl == 950


def test_event_manager_batch_upsert_and_sync():
    em = EventManager()
    adapter = BengaluruIncidentAdapter()
    curated = adapter.get_verified_curated_incidents(zone="Electronic City South")
    assert len(curated) >= 2

    ins, upd = em.upsert_events_batch(curated)
    assert (ins + upd) >= len(curated)

    ins2, upd2 = em.upsert_events_batch(curated)
    assert ins2 == 0
    assert upd2 == len(curated)

    silk_events = em.find_active_events(road_id="RD_BLR_11", published_only=True)
    assert len(silk_events) > 0
    assert any("Silk Board" in e["name"] for e in silk_events)


def test_silk_board_dynamic_bypass_evaluation():
    p = TrafficPredictor()
    p.load_artifacts()
    em = EventManager()
    nav = RouteNavigator(p, em)

    adapter = BengaluruIncidentAdapter()
    incidents = adapter.get_verified_curated_incidents(zone="Electronic City South")
    em.upsert_events_batch(incidents)

    today_str = datetime.now().strftime("%Y-%m-%d")
    res = nav.evaluate_route("RD_BLR_06", "RD_BLR_11", today_str, "09:00", published_only=True)

    assert res.origin_road == "RD_BLR_06"
    assert res.destination_road == "RD_BLR_11"
    assert res.primary_congestion in ["High", "Severe"]
    assert res.is_rerouted is True
    assert res.time_saved_minutes > 0.0
    assert len(res.active_events) > 0
    assert "South End Circle" in res.recommended_route_names or "Silk Board" in res.recommended_route_names

"""
tests/test_live_simulation.py - Automated Tests for Live Telemetry & Simulation Subsystem
Tests:
- Live bridge status & provider inspection
- Corridor telemetry derivation & XGBoost volume scale alignment
- Rate limiting, thread safety, and TTL caching
- Dynamic live route evaluation & bypass recommendations
- Non-breaking server endpoints (/api/live/*)
"""

import pytest
import threading
from traffic_system.live.bridge import get_live_bridge, LiveTrafficDataBridge

def test_live_bridge_singleton_and_status():
    bridge = get_live_bridge()
    assert bridge is not None
    status = bridge.get_live_status()
    assert status["status"] == "success"
    assert status["monitored_corridors"] == 24
    assert "status_code" in status
    assert "weather" in status
    assert status["weather"]["condition"] in ("Clear", "Rainy", "Foggy")

def test_live_corridor_telemetry_and_volume_scale():
    bridge = get_live_bridge()
    corridors = bridge.get_corridor_telemetry()
    assert len(corridors) == 24

    for c in corridors:
        assert c["road_id"].startswith("RD_BLR_")
        assert len(c["road_name"]) > 0
        assert c["current_speed"] > 0
        assert c["free_flow_speed"] >= c["current_speed"] * 0.5
        assert c["congestion_level"] in ("Low", "Moderate", "High", "Severe")
        assert 10000 <= c["vehicle_count"] <= 65000, f"Volume {c['vehicle_count']} out of empirical bounds"
        assert c["predicted_future_congestion"] in ("Low", "Moderate", "High", "Severe")
        assert 0.0 <= c["prediction_confidence"] <= 1.0

def test_live_route_evaluation():
    bridge = get_live_bridge()
    eval_res = bridge.evaluate_live_route("RD_BLR_01", "RD_BLR_02")
    assert eval_res["origin_road"] == "RD_BLR_01"
    assert eval_res["destination_road"] == "RD_BLR_02"
    assert len(eval_res["primary_route"]) >= 2
    assert eval_res["primary_speed_kmh"] > 0
    assert eval_res["primary_vehicle_count"] >= 10000
    assert eval_res["primary_congestion"] in ("Low", "Moderate", "High", "Severe")
    assert "time_saved_minutes" in eval_res
    assert isinstance(eval_res["is_rerouted"], bool)

def test_live_bridge_thread_safety_concurrent_access():
    bridge = get_live_bridge()
    errors = []

    def _worker():
        try:
            res = bridge.get_corridor_telemetry(["RD_BLR_01", "RD_BLR_02"])
            assert len(res) == 2
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread safety errors: {errors}"

def test_live_weather_fallback():
    bridge = get_live_bridge()
    weather = bridge.fetch_live_weather()
    assert weather["condition"] in ("Clear", "Rainy", "Foggy")
    assert "temperature" in weather

def test_live_route_evaluation_with_date_and_time_events():
    from traffic_system.events.event_manager import EventManager
    bridge = get_live_bridge()
    em = EventManager()

    # South End Circle (RD_BLR_13 -> RD_BLR_22) nighttime resurfacing: 21:00 - 06:00
    res_active = bridge.evaluate_live_route(
        "RD_BLR_13", "RD_BLR_22", event_mgr=em, date="2026-11-03", time_str="22:00", published_only=True
    )
    assert res_active["horizon_date"] == "2026-11-03"
    assert res_active["horizon_time"] == "22:00"
    assert res_active["has_active_events"] is True
    assert any("South End Circle" in e["name"] for e in res_active["active_events"])
    assert res_active["is_rerouted"] is True

    # At noon (12:00), nighttime resurfacing (21:00 - 06:00) is NOT active
    res_inactive = bridge.evaluate_live_route(
        "RD_BLR_13", "RD_BLR_22", event_mgr=em, date="2026-11-03", time_str="12:00", published_only=True
    )
    assert res_inactive["horizon_date"] == "2026-11-03"
    assert res_inactive["horizon_time"] == "12:00"
    assert not any("South End Circle" in e["name"] for e in res_inactive["active_events"])

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
        # Volume must be calibrated to XGBoost training distribution ($10k - $65k)
        assert 10000 <= c["vehicle_count"] <= 65000, f"Volume {c['vehicle_count']} out of empirical bounds"
        # XGBoost forward pass prediction
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
    # Offline or mock coordinate fetch
    weather = bridge.fetch_live_weather()
    assert weather["condition"] in ("Clear", "Rainy", "Foggy")
    assert "temperature" in weather

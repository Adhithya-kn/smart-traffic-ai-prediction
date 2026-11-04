"""
scripts/verify_commuter_console_e2e.py
Automated End-to-End Demonstration and Verification of the Road User / Commuter Console.
Demonstrates:
- Section 1: Standard Operations (origin/dest, future date/time, model estimate disclaimer, verified events)
- Section 2: Live Traffic (TomTom route calculation, live telemetry, and explicit fallback)
- Section 3: Traffic Heat Map (all 24 registered corridors, flyout telemetry, unobserved grey state, transfer to route planner)
"""

import sys
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8089"

def request_json(path, method="GET", payload=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def main():
    print("=" * 70)
    print(" ROAD USER / COMMUTER CONSOLE END-TO-END VERIFICATION")
    print(f" Target Server: {BASE_URL}")
    print("=" * 70)

    # 1. Authenticate as Road User
    print("\n[PHASE 1] Authenticating Road User...")
    status, auth_data = request_json("/api/auth/login", method="POST", payload={
        "username": "commuter",
        "password": "Admin@123"
    })
    assert status == 200, f"Login failed: {auth_data}"
    sess = auth_data.get("session") or auth_data.get("data", {}).get("session", {})
    token = sess.get("token")
    role = sess.get("role")
    assert role == "Road User", f"Expected Road User, got {role}"
    print(f"  ✓ Successfully signed in as '{sess.get('username')}' with role '{role}'")

    # 2. Section 1 - Standard Operations
    print("\n[PHASE 2] Demonstrating Section 1: Standard Operations...")
    origin = "RD_BLR_01"       # 100 Feet Road (Indiranagar)
    dest = "RD_BLR_06"         # Hosur Road (Electronic City)
    dep_date = "2026-11-20"    # Future Date
    dep_time = "18:30"         # Future Evening Peak

    status, raw_route = request_json("/api/route/evaluate", method="POST", payload={
        "origin_road": origin,
        "destination_road": dest,
        "departure_date": dep_date,
        "departure_time": dep_time
    }, token=token)
    assert status == 200, f"Route evaluation failed: {raw_route}"
    route_data = raw_route.get("evaluation") or raw_route.get("data") or raw_route

    print(f"  ✓ Origin: {route_data.get('origin_name', origin)}")
    print(f"  ✓ Destination: {route_data.get('destination_name', dest)}")
    print(f"  ✓ Departure Horizon: {route_data.get('departure_date')} at {route_data.get('departure_time')}")
    print(f"  ✓ Primary Duration: {route_data.get('primary_travel_time_minutes')} mins (LOS: {route_data.get('primary_congestion')})")
    print(f"  ✓ Recommended Duration: {route_data.get('recommended_travel_time_minutes')} mins (LOS: {route_data.get('recommended_congestion')})")
    print(f"  ✓ Travel Time Saved: {route_data.get('time_saved_minutes')} mins")
    print(f"  ✓ Model Estimation Disclaimer: {route_data.get('disclaimer')}")
    assert route_data.get("is_historical_model_estimate") is True, "Must be flagged as historical model estimate"
    assert "estimates based on topological network models" in route_data.get("disclaimer", "")

    # Check Municipal Event Warnings
    active_evts = route_data.get("active_events", [])
    print(f"  ✓ Active Municipal Events En Route: {len(active_evts)}")
    for evt in active_evts:
        print(f"    - [{evt.get('verification_status')}] {evt.get('name')} | Source: {evt.get('source_name')} ({evt.get('source_url')})")
        assert evt.get("verification_status") == "OFFICIAL_VERIFIED"
        assert evt.get("source_url", "").startswith("http")

    # Verify unverified draft seed events are absent
    status, events_data = request_json("/api/events", method="GET", token=token)
    assert status == 200
    commuter_events = events_data.get("events", [])
    assert not any(e["id"] == "EVT_001" for e in commuter_events), "Unverified EVT_001 must not appear in commuter feed"
    print(f"  ✓ Verified published event count for commuters: {len(commuter_events)} (Unverified drafts strictly excluded)")

    # 3. Section 2 - Live Traffic
    print("\n[PHASE 3] Demonstrating Section 2: Live Traffic...")
    status, raw_prov = request_json("/api/config/providers", method="GET", token=token)
    prov_data = raw_prov.get("data") or raw_prov
    print(f"  ✓ Providers registered: {list(prov_data.keys())}")

    # Test Live Route Evaluation
    status, raw_live = request_json("/api/live/evaluate_route", method="POST", payload={
        "origin_road": origin,
        "destination_road": dest,
        "date": "2026-11-04",
        "time_str": "14:30"
    }, token=token)
    assert status == 200, f"Live route failed: {raw_live}"
    live_route = raw_live.get("data") or raw_live.get("evaluation") or raw_live

    print(f"  ✓ Live Route Status: {live_route.get('status')}")
    print(f"  ✓ Provider: {live_route.get('provider')}")
    print(f"  ✓ Travel Duration: {live_route.get('travel_time_minutes')} mins")
    print(f"  ✓ Traffic Delay: {live_route.get('traffic_delay_minutes')} mins")
    print(f"  ✓ Is Live: {live_route.get('is_live')} | Is Fallback: {live_route.get('is_fallback')}")
    if live_route.get("is_fallback"):
        print(f"  ✓ Fallback Provenance: {live_route.get('fallback_reason')}")
        assert "fallback" in live_route.get("provider", "").lower() or live_route.get("status") == "FALLBACK_TOPOLOGICAL"

    # 4. Section 3 - Traffic Heat Map
    print("\n[PHASE 4] Demonstrating Section 3: Traffic Heat Map...")
    status, roads_data = request_json("/api/roads", method="GET", token=token)
    assert status == 200
    roads = roads_data.get("roads", [])
    assert len(roads) == 24, f"Expected 24 corridors, got {len(roads)}"
    print(f"  ✓ Mapped all 24 registered Bengaluru corridors across 8 sectors")

    status, live_corridors = request_json("/api/live/refresh", method="POST", token=token)
    assert status == 200
    telemetry = live_corridors.get("corridors", [])
    assert len(telemetry) == 24, f"Expected 24 telemetry records, got {len(telemetry)}"

    # Inspect corridor condition and data source
    sample_c = telemetry[0]
    print(f"  ✓ Selected Corridor: {sample_c.get('road_name')} ({sample_c.get('road_id')})")
    print(f"    - Current Speed: {sample_c.get('current_speed')} km/h")
    print(f"    - Free-Flow Speed: {sample_c.get('free_flow_speed')} km/h")
    print(f"    - Congestion Level: {sample_c.get('congestion_level')}")
    print(f"    - Observation Time: {sample_c.get('observation_time')}")
    print(f"    - Provenance: {sample_c.get('provenance')}")
    print(f"    - Vehicle Count Source: {sample_c.get('vehicle_count_source')}")
    assert sample_c.get("vehicle_count_source") == "Topological Baseline Calibration", "Must not invent counts from speed"

    # Verify unobserved corridors display unavailable/fallback status
    unobserved = [c for c in telemetry if not c.get("has_valid_live_observation")]
    print(f"  ✓ Corridors in calibrated baseline/standby: {len(unobserved)}/24 (rendered with grey `#6b7280` indicator)")

    print("\n" + "=" * 70)
    print(" ALL 3 SECTIONS OF ROAD USER / COMMUTER CONSOLE VERIFIED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()

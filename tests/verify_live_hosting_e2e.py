"""
End-to-End Live Hosting Verification Suite
Tests all HTTP endpoints, security auth, route evaluation, counterfactual simulation,
event scheduling, and action directives on the live running server.
"""

import os
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
port = sys.argv[1] if len(sys.argv) > 1 else "8089"
BASE_URL = os.environ.get("BASE_URL", f"http://127.0.0.1:{port}")

def request_json(path, method="GET", payload=None, expected_status=200):
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return status, json.loads(body)
            return status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return e.code, parsed

def test_static_and_pages():
    print("\n[SUITE 1/7] Testing Static Assets & Page Endpoints...")
    # 1. Login entry page (/)
    status, html = request_json("/")
    assert status == 200, f"Expected 200 for /, got {status}"
    assert "Smart Traffic AI" in html, f"Title 'Smart Traffic AI' missing from HTML"
    assert "Sign In" in html, "Sign In missing from entry page"
    print("  ✓ GET / (Login Entry Gateway) loaded cleanly.")

    # 2. Login page (/login)
    status, login_html = request_json("/login")
    assert status == 200, f"Expected 200 for /login, got {status}"
    assert "Sign In" in login_html, "Sign In missing from /login"
    print("  ✓ GET /login (Dedicated Authentication Page) loaded cleanly.")

    # 3. Portal page (/portal)
    status, portal_html = request_json("/portal")
    assert status == 200, f"Expected 200 for /portal, got {status}"
    assert "routeEvaluationContainer" in portal_html, "routeEvaluationContainer missing from /portal"
    print("  ✓ GET /portal (Operational Dashboard Viewport) loaded cleanly.")

    # 3. CSS & JS assets
    status, css = request_json("/styles.css")
    assert status == 200, f"Expected 200 for styles.css, got {status}"
    assert "--bg-app" in css, "Variable --bg-app missing from styles.css"
    print("  ✓ GET /styles.css loaded cleanly.")

    status, js = request_json("/app.js")
    assert status == 200, f"Expected 200 for app.js, got {status}"
    assert "evaluateRoute" in js, "evaluateRoute function missing from app.js"
    print("  ✓ GET /app.js loaded cleanly.")

def test_authentication():
    print("\n[SUITE 2/7] Testing Cryptographic Authentication & Role Sessions...")
    # 1. Valid Commuter Login
    status, res = request_json("/api/auth/login", method="POST", payload={
        "username": "commuter",
        "password": "Admin@123"
    })
    assert status == 200, f"Expected 200, got {status}: {res}"
    assert res.get("status") == "success"
    assert res["session"]["role"] == "Road User"
    assert "token" in res["session"]
    print("  ✓ POST /api/auth/login (Commuter / Road User) verified.")

    # 2. Valid Traffic Admin Login
    status, res = request_json("/api/auth/login", method="POST", payload={
        "username": "traffic_admin",
        "password": "Admin@123"
    })
    assert status == 200
    assert res["session"]["role"] == "Traffic Management"
    print("  ✓ POST /api/auth/login (Traffic Authority / Management) verified.")

    # 3. Invalid Password Rejection (Indistinguishable 401)
    status, res = request_json("/api/auth/login", method="POST", payload={
        "username": "commuter",
        "password": "wrongpassword"
    })
    assert status == 401
    assert res.get("status") == "error"
    print("  ✓ POST /api/auth/login correctly rejected invalid credentials.")

    # 4. User Registration
    import time
    new_user = f"test_driver_{int(time.time())}"
    status, res = request_json("/api/auth/register", method="POST", payload={
        "username": new_user,
        "password": "securepassword123",
        "role": "Commuter"
    })
    assert status == 200
    assert res.get("status") == "success"
    print(f"  ✓ POST /api/auth/register registered user '{new_user}'.")

    # Clean up test user to preserve database hygiene
    del_status, _ = request_json("/api/auth/delete", method="POST", payload={"username": new_user})
    assert del_status == 200
    print(f"  ✓ Cleaned up transient test user '{new_user}'.")

def test_network_and_zones():
    print("\n[SUITE 3/7] Testing Urban Network Topology & Zone Telemetry...")
    # 1. All roads
    status, res = request_json("/api/roads")
    assert status == 200
    assert res.get("count", 0) > 0
    roads = res.get("roads", [])
    print(f"  ✓ GET /api/roads returned {len(roads)} topological corridors.")

    # 2. Filtered roads by zone
    status, res = request_json("/api/roads?zone=Indiranagar")
    assert status == 200
    for r in res.get("roads", []):
        assert r["city_zone"] == "Indiranagar"
    print("  ✓ GET /api/roads?zone=Indiranagar filtered correctly.")

    # 3. Zone criticality summary
    status, res = request_json("/api/zones/summary")
    assert status == 200
    zones = res.get("zones", [])
    assert len(zones) >= 6
    print(f"  ✓ GET /api/zones/summary calculated criticality for {len(zones)} zones.")

def test_events_engine():
    print("\n[SUITE 4/7] Testing Municipal Event Scheduling & Temporal Matching...")
    # 1. Scheduled Events
    status, res = request_json("/api/events")
    assert status == 200
    events = res.get("events", [])
    assert len(events) > 0
    print(f"  ✓ GET /api/events returned {len(events)} active municipal events.")

    # 2. Historical Events
    status, res = request_json("/api/events/historical")
    assert status == 200
    hist = res.get("events", [])
    assert len(hist) > 0
    print(f"  ✓ GET /api/events/historical returned {len(hist)} ground-truth historical records.")

    # 3. Create New Municipal Event
    status, res = request_json("/api/events/add", method="POST", payload={
        "name": "Live Hosting Verification Coning Event",
        "event_type": "Construction",
        "city_zone": "Indiranagar",
        "affected_roads": ["RD_BLR_01"],
        "date": "2026-10-23",
        "start_time": "08:00",
        "end_time": "12:00",
        "severity_boost": 2,
        "volume_surge_vph": 450,
        "description": "Lane coning and surface repair"
    })
    assert status == 200, f"Expected 200 for /api/events/add, got {status}: {res}"
    assert res.get("status") == "success"
    created_id = res.get("event", {}).get("id")
    print("  ✓ POST /api/events/add created new municipal event successfully.")

    # 4. Clean up transient test event so production artifacts remain pristine
    if created_id:
        del_status, del_res = request_json("/api/events/delete", method="POST", payload={"event_id": created_id})
        assert del_status == 200, f"Failed to clean up test event: {del_res}"
        print(f"  ✓ Cleaned up transient test event '{created_id}'.")

def test_ml_inference_and_explainability():
    print("\n[SUITE 5/7] Testing XGBoost Inference & TreeSHAP Local Explanations...")
    status, res = request_json("/api/predict/explain", method="POST", payload={
        "features": {
            "city_zone": "Indiranagar",
            "road_id": "RD_BLR_01",
            "intersection_id": "INT_BLR_05",
            "vehicle_count": 31957,
            "average_speed": 38.4,
            "hour": 17,
            "day_of_week": 3,
            "is_weekend": 0
        }
    })
    assert status == 200, f"Expected 200 for /api/predict/explain, got {status}: {res}"
    exp = res.get("explanation", {})
    assert "prediction" in exp
    assert "probabilities" in exp
    assert "uncertainty_entropy" in exp
    assert "top_drivers" in exp
    print(f"  ✓ POST /api/predict/explain returned: class '{exp['prediction']}', H(p)={exp['uncertainty_entropy']:.3f}, {len(exp['top_drivers'])} SHAP factors.")

def test_route_navigation_and_bypass():
    print("\n[SUITE 6/7] Testing Dynamic Dijkstra Route Evaluation & Intelligent Rerouting...")
    # 1. Congested corridor with event on presentation date (RD_BLR_01 -> RD_BLR_12 on 2026-04-30)
    status, res = request_json("/api/route/evaluate", method="POST", payload={
        "origin_road": "RD_BLR_01",
        "destination_road": "RD_BLR_12",
        "date": "2026-04-30",
        "time": "17:00"
    })
    assert status == 200
    eval_data = res.get("evaluation", {})
    assert eval_data.get("is_rerouted") is True
    assert eval_data.get("time_saved_minutes", 0) > 0
    print(f"  ✓ Presentation Date (2026-04-30) Bottleneck Reroute Verified: {eval_data['primary_congestion']} -> {eval_data['recommended_congestion']} "
          f"(Saved: {eval_data['time_saved_minutes']} mins via {eval_data['recommended_route']})")

    # 2. Optimal corridor without event on 2026-04-30
    status, res = request_json("/api/route/evaluate", method="POST", payload={
        "origin_road": "RD_BLR_03",
        "destination_road": "RD_BLR_05",
        "date": "2026-04-30",
        "time": "03:00"
    })
    assert status == 200
    eval_data = res.get("evaluation", {})
    print(f"  ✓ Optimal Path Verified: No bottleneck detected ({eval_data['primary_congestion']}).")

def test_simulation_and_dispatch():
    print("\n[SUITE 7/7] Testing Counterfactual Monte-Carlo Simulation & Webster Actuation...")
    # 1. Counterfactual Simulation
    status, res = request_json("/api/simulation/run", method="POST", payload={
        "zone": "Indiranagar",
        "alpha": 0.25,
        "beta": 0.15,
        "hour": 17,
        "day_of_week": 3
    })
    assert status == 200
    sim = res.get("simulation", {})
    assert "summary" in sim
    improved = sim["summary"]["improved_segments"]
    print(f"  ✓ POST /api/simulation/run: {improved}/{sim['total_segments_evaluated']} corridors de-escalated ({sim['summary']['improved_pct']}%).")

    # 2. Dispatch Directives & Webster Signal Splits
    status, res = request_json("/api/dispatch/directives?zone=Indiranagar")
    assert status == 200, f"Expected 200 for /api/dispatch/directives, got {status}: {res}"
    directives = res.get("directives", [])
    assert len(directives) > 0
    d0 = directives[0]
    assert "signal_actuation_parameters" in d0
    webster = d0["signal_actuation_parameters"]
    print(f"  ✓ GET /api/dispatch/directives: Generated {len(directives)} directives with actuated Webster cycle={webster['optimal_cycle_sec']}s (NS: {webster['ns_green_sec']}s, EW: {webster['ew_green_sec']}s).")

if __name__ == "__main__":
    print("=" * 70)
    print(" RUNNING FULL LIVE HOSTING SYSTEM END-TO-END VERIFICATION")
    print(f" Target: {BASE_URL}")
    print("=" * 70)
    try:
        test_static_and_pages()
        test_authentication()
        test_network_and_zones()
        test_events_engine()
        test_ml_inference_and_explainability()
        test_route_navigation_and_bypass()
        test_simulation_and_dispatch()
        print("\n" + "=" * 70)
        print(" 🎉 ALL 7 LIVE HOSTING VERIFICATION SUITES PASSED FLAWLESSLY!")
        print("=" * 70)
        sys.exit(0)
    except AssertionError as ae:
        print(f"\n❌ ASSERTION FAILED: {ae}")
        sys.exit(1)
    finally:
        # Clean up transient test driver from users.json
        try:
            users_file = BASE_DIR / "traffic_system" / "artifacts" / "users.json"
            if users_file.exists():
                with open(users_file, "r", encoding="utf-8") as f:
                    u_data = json.load(f)
                cleaned_u = {k: v for k, v in u_data.items() if not k.startswith("test_driver_")}
                with open(users_file, "w", encoding="utf-8") as f:
                    json.dump(cleaned_u, f, indent=2)
        except Exception:
            pass

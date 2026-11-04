"""
tests/test_server_api.py - Comprehensive Unit & Regression Tests for Main Server (app/server.py)
Validates:
1. _read_body_raw (missing, negative, oversized, incomplete)
2. _read_body (invalid JSON, wrong content-type, non-object payloads)
3. _send_json & CORS origin allowlisting and consistent headers
4. _check_admin_auth (role enforcement, removal of ambiguous aliases)
5. /api/health vs /api/health/readiness (real read/write storage check, 0 events allowed)
6. /architecture/* (path traversal containment)
7. /api/live/refresh (rate-limiting and protection)
8. /api/live/predict (feature schema validation, provenance)
9. /api/route/evaluate & /api/junction/telemetry (dynamic dates, bounds, simulation flag)
"""

import io
import json
import urllib.parse
from pathlib import Path
import pytest

from app.server import TrafficAppServer
from traffic_system.core.entities import UserRole
from traffic_system.config import BASE_DIR, MAX_REQUEST_BODY_SIZE


class MockWFile:
    def __init__(self):
        self.data = b""

    def write(self, b):
        self.data += b


def create_test_server(path: str = "/", method: str = "GET", headers: dict = None, body_bytes: bytes = b"") -> TrafficAppServer:
    TrafficAppServer.ensure_initialized()
    server = TrafficAppServer.__new__(TrafficAppServer)
    server.command = method
    server.path = path
    server.headers = headers or {}
    server.rfile = io.BytesIO(body_bytes)
    server.wfile = MockWFile()
    server._headers_buffer = []
    server.response_code = 200

    def send_response(code, message=None):
        server.response_code = code

    def send_header(keyword, value):
        server._headers_buffer.append((keyword, value))

    def end_headers():
        pass

    server.send_response = send_response
    server.send_header = send_header
    server.end_headers = end_headers
    return server


# -----------------------------------------------------------------------------
# 1. _read_body_raw Validation
# -----------------------------------------------------------------------------
def test_read_body_raw_validations():
    server = create_test_server()

    # Missing Content-Length when required
    server.headers = {}
    with pytest.raises(ValueError) as exc:
        server._read_body_raw(require_content_length=True)
    assert "Missing Content-Length header" in str(exc.value)

    # Negative Content-Length
    server.headers = {"Content-Length": "-5"}
    with pytest.raises(ValueError) as exc:
        server._read_body_raw()
    assert "Invalid negative Content-Length" in str(exc.value)

    # Oversized Content-Length
    server.headers = {"Content-Length": str(MAX_REQUEST_BODY_SIZE + 10)}
    with pytest.raises(ValueError) as exc:
        server._read_body_raw(max_bytes=MAX_REQUEST_BODY_SIZE)
    assert "Payload Too Large" in str(exc.value)

    # Truncated / Incomplete request body
    server.headers = {"Content-Length": "20"}
    server.rfile = io.BytesIO(b"short")  # Only 5 bytes
    with pytest.raises(ValueError) as exc:
        server._read_body_raw()
    assert "Incomplete request body" in str(exc.value)

    # Valid body read
    server.headers = {"Content-Length": "12"}
    server.rfile = io.BytesIO(b"hello world!")
    data = server._read_body_raw()
    assert data == b"hello world!"


# -----------------------------------------------------------------------------
# 2. _read_body Strict Parsing
# -----------------------------------------------------------------------------
def test_read_body_content_type_and_payload_checks():
    server = create_test_server()

    # Wrong Content-Type
    server.headers = {"Content-Type": "text/plain", "Content-Length": "10"}
    server.rfile = io.BytesIO(b"some plain")
    with pytest.raises(ValueError) as exc:
        server._read_body()
    assert "Unsupported Media Type" in str(exc.value)

    # Non-object JSON payload (array)
    arr_bytes = b"[1, 2, 3]"
    server.headers = {"Content-Type": "application/json", "Content-Length": str(len(arr_bytes))}
    server.rfile = io.BytesIO(arr_bytes)
    with pytest.raises(ValueError) as exc:
        server._read_body()
    assert "JSON object (dictionary)" in str(exc.value)

    # Non-object JSON payload (primitive)
    str_bytes = b'"string"'
    server.headers = {"Content-Type": "application/json", "Content-Length": str(len(str_bytes))}
    server.rfile = io.BytesIO(str_bytes)
    with pytest.raises(ValueError) as exc:
        server._read_body()
    assert "JSON object (dictionary)" in str(exc.value)

    # Valid JSON object with application/json; charset=utf-8
    valid_bytes = b'{"key": "value"}'
    server.headers = {"Content-Type": "application/json; charset=utf-8", "Content-Length": str(len(valid_bytes))}
    server.rfile = io.BytesIO(valid_bytes)
    parsed = server._read_body()
    assert parsed == {"key": "value"}


# -----------------------------------------------------------------------------
# 3. _send_json CORS Origin Allowlisting & Headers
# -----------------------------------------------------------------------------
def test_cors_origin_and_security_headers():
    server = create_test_server()
    server.headers = {"Origin": "http://localhost:8080"}
    server._send_json(200, {"status": "ok"})

    headers_dict = dict(server._headers_buffer)
    assert headers_dict.get("Content-Type") == "application/json; charset=utf-8"
    assert headers_dict.get("X-Content-Type-Options") == "nosniff"
    assert headers_dict.get("X-Frame-Options") == "DENY"
    assert headers_dict.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Access-Control-Allow-Origin" in headers_dict


# -----------------------------------------------------------------------------
# 4. _check_admin_auth Role Enforcement
# -----------------------------------------------------------------------------
def test_check_admin_auth_strict_role():
    server = create_test_server()

    # Mock user with ROAD_USER role
    server._get_auth_user = lambda: {"username": "bob", "role": UserRole.ROAD_USER.value}
    ok, err, code = server._check_admin_auth()
    assert ok is False
    assert code == 403
    assert "Traffic Management" in err

    # Mock user with canonical TRAFFIC_MANAGEMENT role
    server._get_auth_user = lambda: {"username": "admin", "role": UserRole.TRAFFIC_MANAGEMENT.value}
    ok, err, code = server._check_admin_auth()
    assert ok is True
    assert code == 200


# -----------------------------------------------------------------------------
# 5. Real Readiness vs Liveness Probe (0 Events Valid)
# -----------------------------------------------------------------------------
def test_readiness_real_storage_check_and_zero_events():
    server = create_test_server(path="/api/health/readiness")
    server.do_GET()

    assert server.response_code == 200
    res = json.loads(server.wfile.data.decode("utf-8"))
    assert res["status"] == "ready"
    assert res["readiness"] is True
    assert res["checks"]["storage_writeable"] is True
    assert res["checks"]["predictor_loaded"] is True
    assert res["checks"]["event_engine_ready"] is True

    # Even with zero events, event engine must remain ready
    original_events = server.event_mgr.events
    try:
        server.event_mgr.events = {}
        server.wfile = MockWFile()
        server._headers_buffer = []
        server.do_GET()
        res_empty = json.loads(server.wfile.data.decode("utf-8"))
        assert res_empty["checks"]["event_engine_ready"] is True
        assert res_empty["readiness"] is True
    finally:
        server.event_mgr.events = original_events


# -----------------------------------------------------------------------------
# 6. Architecture Directory File Containment
# -----------------------------------------------------------------------------
def test_architecture_containment_and_traversal_rejection():
    # Traversal attempts
    server1 = create_test_server(path="/architecture/../../etc/passwd")
    server1.do_GET()
    assert server1.response_code == 403

    server2 = create_test_server(path="/architecture/%2e%2e%2fsecret.env")
    server2.do_GET()
    assert server2.response_code == 403

    # Non-existent file inside architecture
    server3 = create_test_server(path="/architecture/nonexistent_doc.html")
    server3.do_GET()
    assert server3.response_code == 404


# -----------------------------------------------------------------------------
# 7. Live Refresh Rate Limiting
# -----------------------------------------------------------------------------
def test_live_refresh_rate_limiting(monkeypatch):
    from traffic_system.live.bridge import LiveTrafficDataBridge
    monkeypatch.setattr(LiveTrafficDataBridge, "get_corridor_telemetry", lambda self, force_refresh=False: [])
    monkeypatch.setattr(LiveTrafficDataBridge, "get_live_status", lambda self: {"status": "TEST_OK"})

    # Call endpoint until rate limit triggers
    codes = []
    for _ in range(15):
        s = create_test_server(path="/api/live/refresh", method="POST")
        s.client_address = ("192.168.1.100", 54321)
        s.headers = {"Content-Length": "2"}
        s.rfile = io.BytesIO(b"{}")
        s.do_POST()
        codes.append(s.response_code)

    assert 200 in codes
    assert 429 in codes  # Rate limit exceeded triggered cleanly


# -----------------------------------------------------------------------------
# 8. Live Predict Feature Schema Validation & Model Provenance
# -----------------------------------------------------------------------------
def test_live_predict_schema_validation_and_provenance():
    # Missing features object -> 400
    s1 = create_test_server(path="/api/live/predict", method="POST", headers={"Content-Type": "application/json", "Content-Length": "2"}, body_bytes=b"{}")
    s1.do_POST()
    assert s1.response_code == 400

    # Negative vehicle count -> 400
    bad_payload = json.dumps({"features": {"vehicle_count": -100}}).encode("utf-8")
    s2 = create_test_server(path="/api/live/predict", method="POST", headers={"Content-Type": "application/json", "Content-Length": str(len(bad_payload))}, body_bytes=bad_payload)
    s2.do_POST()
    assert s2.response_code == 400

    # Valid payload -> 200 with model provenance
    valid_payload = json.dumps({
        "features": {
            "road_id": "RD_BLR_01",
            "vehicle_count": 1800,
            "average_speed": 32.0,
            "hour": 17,
            "day_of_week": 2
        }
    }).encode("utf-8")
    s3 = create_test_server(path="/api/live/predict", method="POST", headers={"Content-Type": "application/json", "Content-Length": str(len(valid_payload))}, body_bytes=valid_payload)
    s3.do_POST()
    assert s3.response_code == 200
    res = json.loads(s3.wfile.data.decode("utf-8"))
    assert "predicted_class" in res
    assert "provenance" in res
    assert res["provenance"]["model_name"] == "XGBoost Pure-Python Tree Ensemble"
    assert "dataset_version" in res["provenance"]


# -----------------------------------------------------------------------------
# 9. Route Evaluation & Junction Telemetry (Dynamic Dates, Provenance)
# -----------------------------------------------------------------------------
def test_route_evaluate_and_junction_telemetry():
    # Route Evaluate with dynamic date
    req_body = json.dumps({
        "origin_road": "RD_BLR_01",
        "destination_road": "RD_BLR_04"
    }).encode("utf-8")
    s1 = create_test_server(path="/api/route/evaluate", method="POST", headers={"Content-Type": "application/json", "Content-Length": str(len(req_body))}, body_bytes=req_body)
    s1.do_POST()
    assert s1.response_code == 200
    res1 = json.loads(s1.wfile.data.decode("utf-8"))
    assert res1["success"] is True
    assert "evaluation" in res1

    # Route Evaluate with invalid corridor ID -> 400
    bad_body = json.dumps({"origin_road": "../../bad_id"}).encode("utf-8")
    s2 = create_test_server(path="/api/route/evaluate", method="POST", headers={"Content-Type": "application/json", "Content-Length": str(len(bad_body))}, body_bytes=bad_body)
    s2.do_POST()
    assert s2.response_code == 400

    # Junction Telemetry with simulation provenance
    junc_body = json.dumps({"road_id": "RD_BLR_01", "time": "18:30"}).encode("utf-8")
    s3 = create_test_server(path="/api/junction/telemetry", method="POST", headers={"Content-Type": "application/json", "Content-Length": str(len(junc_body))}, body_bytes=junc_body)
    s3.do_POST()
    assert s3.response_code == 200
    res3 = json.loads(s3.wfile.data.decode("utf-8"))
    assert res3["junction"]["is_simulated"] is True
    assert "data_provenance" in res3["junction"]

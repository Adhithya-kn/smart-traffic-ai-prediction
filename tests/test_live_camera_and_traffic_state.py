"""
tests/test_live_camera_and_traffic_state.py - Unit & Integration Tests for Live Camera & Traffic State

Tests:
1. Live camera frame ingestion (POST /api/vision/live/frame) with real image decodes.
2. Heterogeneous vehicle classification (Cars, Buses, Autos, Bikes, Trucks).
3. TrafficMeasurement ingestion into LiveTrafficDataBridge (POST /api/traffic-state/ingest).
4. Corridor state queries (GET /api/traffic-state/{corridor_id}).
5. UVH-26 Indian traffic model class mapping and canonicalization.
"""

import base64
import cv2
import numpy as np
import pytest

from traffic_system.computer_vision.detector import VehicleDetector, get_vehicle_detector
from traffic_system.core.measurement import (
    TrafficMeasurement,
    MeasurementValidationError,
    canonicalize_class,
    CANONICAL_CLASSES,
    VEHICLE_CLASSES
)
from traffic_system.core.entities import UserRole
from traffic_system.live.bridge import get_live_bridge
from app.routes.vision_routes import get_vision_handler


def test_canonicalize_class_uvh26_aliases():
    """Verify UVH-26 specific labels map cleanly to canonical vehicle classes."""
    assert canonicalize_class("Hatchback") == "car"
    assert canonicalize_class("Sedan") == "car"
    assert canonicalize_class("SUV") == "car"
    assert canonicalize_class("MUV") == "car"
    assert canonicalize_class("Three-wheeler") == "auto_rickshaw"
    assert canonicalize_class("Two-wheeler") == "motorcycle"
    assert canonicalize_class("Mini-bus") == "bus"
    assert canonicalize_class("Tempo-traveller") == "lcv"
    assert canonicalize_class("LCV") == "lcv"
    assert canonicalize_class("Others") == "unknown"


def test_detector_class_map_and_canonicalization():
    """Verify VehicleDetector populates class_map and handles canonical classes."""
    detector = get_vehicle_detector()
    assert detector.is_yolo_active is True
    assert isinstance(detector.class_map, dict)
    assert len(detector.class_map) > 0

    # Ensure all mapped classes are canonical
    for cls_id, canonical_name in detector.class_map.items():
        assert canonical_name in CANONICAL_CLASSES


def test_live_frame_processing_valid_image():
    """Send an encoded synthetic frame to handle_process_live_frame and verify response."""
    handler = get_vision_handler()
    user_admin = {"username": "admin", "role": UserRole.TRAFFIC_MANAGEMENT.value}

    # Create synthetic test frame (720x1280)
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(img, (200, 300), (400, 500), (200, 200, 200), -1)
    _, buffer = cv2.imencode(".jpg", img)
    b64_str = base64.b64encode(buffer).decode("utf-8")

    code, resp = handler.handle_process_live_frame(
        {"image": f"data:image/jpeg;base64,{b64_str}"},
        requesting_user=user_admin
    )

    assert code == 200
    assert resp["success"] is True
    assert "data" in resp
    data = resp["data"]
    assert "class_counts" in data
    assert "auto_rickshaw" in data["class_counts"]
    assert "car" in data["class_counts"]
    assert "bus" in data["class_counts"]
    assert "lcv" in data["class_counts"]
    assert "total_pcu" in data
    assert "mean_speed_kmh" in data
    assert "detections" in data


def test_live_frame_processing_invalid_payloads():
    """Verify rejection of empty, corrupted, or non-dict payloads."""
    handler = get_vision_handler()

    # Non-dict
    code, resp = handler.handle_process_live_frame([])
    assert code == 400

    # Corrupt base64
    code, resp = handler.handle_process_live_frame({"image": "not_valid_base64!!!"})
    assert code == 400
    assert resp["success"] is False


def test_bridge_inject_traffic_measurement_and_query():
    """Verify LiveTrafficDataBridge ingests a valid TrafficMeasurement and updates corridor state."""
    bridge = get_live_bridge()

    measurement_dict = {
        "measurement_id": "msr_test_live_01",
        "camera_id": "CAM_BLR_04_NORTH",
        "corridor_id": "RD_BLR_04",
        "capture_start": "2026-11-04T10:00:00+05:30",
        "capture_end": "2026-11-04T10:05:00+05:30",
        "interval_s": 300.0,
        "counts": {
            "car": 120,
            "motorcycle": 85,
            "auto_rickshaw": 40,
            "bus": 15,
            "lcv": 10,
            "truck": 5,
            "bicycle": 2,
            "pedestrian": 0,
            "unknown": 0
        },
        "flow": {
            "vph": 3324.0,
            "pcu_per_h": 2850.0,
            "source": "counted_vehicles"
        },
        "occupancy_pct": 38.5,
        "speed": {
            "value_kmh": 26.5,
            "method": "proxy",
            "calibrated": False
        },
        "provenance": {
            "source": "live_camera_feed",
            "is_live": True,
            "is_simulated": False,
            "quality_flags": []
        }
    }

    # Ingest into bridge
    res = bridge.inject_traffic_measurement(measurement_dict)
    assert res["status"] == "success"
    assert res["corridor_id"] == "RD_BLR_04"
    assert "telemetry" in res
    assert "next_hour_forecast" in res
    assert "webster_signal_actuation" in res

    # Query state from bridge
    state = bridge.get_corridor_state("RD_BLR_04")
    assert state is not None
    assert state["road_id"] == "RD_BLR_04"
    assert state["current_speed"] == 26.5
    assert "last_measurement" in state
    assert state["last_measurement"]["measurement_id"] == "msr_test_live_01"
    bridge.clear_cache()


def test_bridge_inject_invalid_measurement_raises():
    """Verify that malformed or empty measurement payloads raise MeasurementValidationError."""
    bridge = get_live_bridge()

    # Missing counts and flow
    with pytest.raises(MeasurementValidationError):
        bridge.inject_traffic_measurement({
            "corridor_id": "RD_BLR_04",
            "capture_start": "2026-11-04T10:00:00+05:30",
            "capture_end": "2026-11-04T10:05:00+05:30"
        })

    # Invalid corridor format
    with pytest.raises(MeasurementValidationError):
        bridge.inject_traffic_measurement({
            "corridor_id": "INVALID_CORRIDOR_NAME",
            "counts": {"car": 10}
        })


def test_server_traffic_state_endpoints():
    """Verify HTTP request dispatching for traffic-state endpoints on TrafficAppServer."""
    import io
    import json
    from app.server import TrafficAppServer
    from traffic_system.core.security import SecurityManager

    import time
    TrafficAppServer.ensure_initialized()
    sec = TrafficAppServer.security
    admin_token = "tok_test_admin_xyz"
    commuter_token = "tok_test_commuter_xyz"
    sec.users["admin"] = {"username": "admin", "role": UserRole.TRAFFIC_MANAGEMENT.value}
    sec.users["commuter"] = {"username": "commuter", "role": UserRole.ROAD_USER.value}
    sec.sessions[admin_token] = {
        "username": "admin",
        "created_at": time.time()
    }
    sec.sessions[commuter_token] = {
        "username": "commuter",
        "created_at": time.time()
    }

    # 1. GET /api/traffic-state/RD_BLR_04
    server_get = TrafficAppServer.__new__(TrafficAppServer)
    server_get.path = "/api/traffic-state/RD_BLR_04"
    server_get.command = "GET"
    server_get.headers = {}
    server_get.wfile = io.BytesIO()
    server_get.send_response = lambda code: None
    server_get.send_header = lambda k, v: None
    server_get.end_headers = lambda: None

    server_get.do_GET()
    server_get.wfile.seek(0)
    data = json.loads(server_get.wfile.read().decode("utf-8"))
    assert data["success"] is True
    assert data["corridor_id"] == "RD_BLR_04"
    assert "state" in data

    # 2. GET /api/traffic-state/INVALID_ROAD -> 404
    server_get_err = TrafficAppServer.__new__(TrafficAppServer)
    server_get_err.path = "/api/traffic-state/NONEXISTENT_ROAD"
    server_get_err.command = "GET"
    server_get_err.headers = {}
    server_get_err.wfile = io.BytesIO()
    server_get_err.send_response = lambda code: None
    server_get_err.send_header = lambda k, v: None
    server_get_err.end_headers = lambda: None

    server_get_err.do_GET()
    server_get_err.wfile.seek(0)
    err_data = json.loads(server_get_err.wfile.read().decode("utf-8"))
    assert err_data["success"] is False
    assert err_data["code"] == 404

    # 3. POST /api/traffic-state/ingest without token -> 401
    server_post_anon = TrafficAppServer.__new__(TrafficAppServer)
    server_post_anon.path = "/api/traffic-state/ingest"
    server_post_anon.command = "POST"
    server_post_anon.headers = {"Content-Length": "2"}
    server_post_anon.rfile = io.BytesIO(b'{}')
    server_post_anon.wfile = io.BytesIO()
    server_post_anon.send_response = lambda code: None
    server_post_anon.send_header = lambda k, v: None
    server_post_anon.end_headers = lambda: None

    server_post_anon.do_POST()
    server_post_anon.wfile.seek(0)
    anon_resp = json.loads(server_post_anon.wfile.read().decode("utf-8"))
    assert anon_resp["success"] is False
    assert anon_resp["code"] == 401

    # 4. POST /api/traffic-state/ingest with commuter token -> 403
    server_post_commuter = TrafficAppServer.__new__(TrafficAppServer)
    server_post_commuter.path = "/api/traffic-state/ingest"
    server_post_commuter.command = "POST"
    server_post_commuter.headers = {
        "Authorization": f"Bearer {commuter_token}",
        "Content-Length": "2"
    }
    server_post_commuter.rfile = io.BytesIO(b'{}')
    server_post_commuter.wfile = io.BytesIO()
    server_post_commuter.send_response = lambda code: None
    server_post_commuter.send_header = lambda k, v: None
    server_post_commuter.end_headers = lambda: None

    server_post_commuter.do_POST()
    server_post_commuter.wfile.seek(0)
    commuter_resp = json.loads(server_post_commuter.wfile.read().decode("utf-8"))
    assert commuter_resp["success"] is False
    assert commuter_resp["code"] == 403

    # 5. POST /api/traffic-state/ingest with admin token and valid measurement -> 200
    msr_body = json.dumps({
        "measurement_id": "msr_http_test_01",
        "corridor_id": "RD_BLR_01",
        "capture_start": "2026-11-04T12:00:00+05:30",
        "capture_end": "2026-11-04T12:05:00+05:30",
        "interval_s": 300.0,
        "counts": {"car": 45, "auto_rickshaw": 20, "bus": 8},
        "flow": {"vph": 876.0, "pcu_per_h": 950.0},
        "speed": {"value_kmh": 22.0, "method": "proxy"},
        "provenance": {"source": "manual_ingest"}
    }).encode("utf-8")

    server_post_admin = TrafficAppServer.__new__(TrafficAppServer)
    server_post_admin.path = "/api/traffic-state/ingest"
    server_post_admin.command = "POST"
    server_post_admin.headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Length": str(len(msr_body))
    }
    server_post_admin.rfile = io.BytesIO(msr_body)
    server_post_admin.wfile = io.BytesIO()
    server_post_admin.send_response = lambda code: None
    server_post_admin.send_header = lambda k, v: None
    server_post_admin.end_headers = lambda: None

    server_post_admin.do_POST()
    server_post_admin.wfile.seek(0)
    admin_resp = json.loads(server_post_admin.wfile.read().decode("utf-8"))
    assert admin_resp["success"] is True
    assert admin_resp["status"] == "success"
    assert "data" in admin_resp
    get_live_bridge().clear_cache()

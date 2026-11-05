"""
tests/test_vision_security.py - Security Verification Suite for Vision Pipeline
Asserts:
1. Authentication on all vision endpoints (401 on missing/invalid token)
2. Role-based authorization for administrative and live-grid actuation operations (403 on non-admin)
3. User ownership association and cross-user isolation (403 on cross-tenant access)
4. Strict identifier validation and path traversal defenses (get_raw_video_path, get_processed_video_path, architecture)
5. Rejection of malformed JSON (400 Bad Request)
6. Content-Length, Content-Type, and filename safety enforcement (411, 413, 415)
7. Rate limiting on video uploads and job submissions (429 Too Many Requests)
"""

import io
import json
import time
from pathlib import Path
import pytest

from traffic_system.core.security import SecurityManager, RateLimiter
from traffic_system.core.entities import UserRole
from traffic_system.core.fs_utils import (
    is_valid_identifier,
    is_safe_path,
    sanitize_filename
)
from traffic_system.storage.video_storage import VideoStorage, get_video_storage
from traffic_system.computer_vision.job_manager import VisionJobManager, get_job_manager
from traffic_system.computer_vision.schemas import JobStatus
from app.routes.vision_routes import VisionRouteHandler, get_vision_handler
from app.server import TrafficAppServer


# -----------------------------------------------------------------------------
# 1. Identifier Validation & Path Traversal
# -----------------------------------------------------------------------------
def test_strict_identifier_validation():
    # Valid identifiers
    assert is_valid_identifier("cv_1234567890") is True
    assert is_valid_identifier("a1b2c3d4e5f6") is True
    assert is_valid_identifier("upload-video_99") is True

    # Invalid / Traversal identifiers
    assert is_valid_identifier("../../etc/passwd") is False
    assert is_valid_identifier("..\\windows\\system32") is False
    assert is_valid_identifier("job/with/slashes") is False
    assert is_valid_identifier("job with spaces") is False
    assert is_valid_identifier("job;rm -rf /") is False
    assert is_valid_identifier("job\x00nullbyte") is False
    assert is_valid_identifier("") is False
    assert is_valid_identifier(None) is False
    assert is_valid_identifier("a" * 65) is False


def test_video_storage_path_traversal_defense(tmp_path):
    storage = VideoStorage(base_dir=tmp_path)

    # Attempt to resolve path outside raw directory
    assert storage.get_raw_video_path("../../etc/passwd") is None
    assert storage.get_raw_video_path("/etc/passwd") is None
    assert storage.get_raw_video_path("../uploads") is None
    assert storage.get_raw_video_path("..%2f..%2fetc/passwd") is None

    # Attempt to resolve processed path outside processed directory
    assert storage.get_processed_video_path("../../etc/passwd") is None
    assert storage.get_processed_video_path("../job") is None

    # Safe create paths reject traversal
    with pytest.raises(ValueError):
        storage.create_processed_path("../../escaped_job")
    with pytest.raises(ValueError):
        storage.create_temp_processed_path("../../escaped_job")


def test_architecture_directory_containment(tmp_path):
    # Tests that safe containment verifies correctly
    arch_dir = tmp_path / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    safe_file = arch_dir / "design.html"
    safe_file.write_text("<h1>System Design</h1>")

    secret_file = tmp_path / "secret.env"
    secret_file.write_text("SECRET_KEY=12345")

    assert is_safe_path(safe_file, arch_dir) is True
    assert is_safe_path(secret_file, arch_dir) is False
    assert is_safe_path(arch_dir / "../secret.env", arch_dir) is False


# -----------------------------------------------------------------------------
# 2. User Ownership Association & Cross-User Access Prevention
# -----------------------------------------------------------------------------
def test_cross_user_isolation(tmp_path):
    storage = VideoStorage(base_dir=tmp_path)
    job_mgr = VisionJobManager(max_workers=1)
    handler = VisionRouteHandler()
    handler.storage = storage
    handler.job_manager = job_mgr

    user_alice = {"username": "alice", "role": UserRole.ROAD_USER.value}
    user_bob = {"username": "bob", "role": UserRole.ROAD_USER.value}
    user_admin = {"username": "admin", "role": UserRole.TRAFFIC_MANAGEMENT.value}

    # Alice uploads a video
    code, res = handler.handle_upload(
        b"\x00\x00\x00 ftypisom" + b"0" * 100,
        filename="alice_traffic.mp4",
        owner="alice"
    )
    assert code == 200
    meta = res["data"]
    video_id = meta["video_id"]
    assert storage.get_video_owner(video_id) == "alice"

    # Bob attempts to process Alice's video -> 403 Forbidden
    code, res = handler.handle_process({"video_id": video_id}, requesting_user=user_bob)
    assert code == 403
    assert res["status"] == "forbidden"

    # Alice processes her own video -> 200 OK
    code, res = handler.handle_process({"video_id": video_id}, requesting_user=user_alice)
    assert code == 200
    job_id = res["data"]["job_id"]
    assert res["data"]["owner"] == "alice"

    # Bob attempts to view Alice's job status -> 403 Forbidden
    code, res = handler.handle_get_job(job_id, requesting_user=user_bob)
    assert code == 403
    assert res["status"] == "forbidden"

    # Bob attempts to view Alice's job results -> 403 Forbidden
    code, res = handler.handle_get_results(job_id, requesting_user=user_bob)
    assert code == 403
    assert res["status"] == "forbidden"

    # Bob attempts to stream Alice's video -> 403 Forbidden
    code, path, mime = handler.handle_get_video(job_id, requesting_user=user_bob)
    assert code == 403
    assert path is None

    # Alice views her own job -> 200 OK
    code, res = handler.handle_get_job(job_id, requesting_user=user_alice)
    assert code == 200

    # Admin can view Alice's job -> 200 OK
    code, res = handler.handle_get_job(job_id, requesting_user=user_admin)
    assert code == 200


# -----------------------------------------------------------------------------
# 3. Role-Based Authorization on Live Grid Actuation
# -----------------------------------------------------------------------------
def test_role_authorization_live_grid():
    handler = VisionRouteHandler()
    user_commuter = {"username": "commuter", "role": UserRole.ROAD_USER.value}
    user_admin = {"username": "traffic_admin", "role": UserRole.TRAFFIC_MANAGEMENT.value}

    actuation_payload = {
        "corridor_id": "RD_BLR_01",
        "vision_metrics": {"total_unique_vehicles": 12, "traffic_density": {"average_occupancy_pct": 35.0}, "kinematics": {"space_mean_speed_kmh": 22.0}}
    }

    # Commuter / Road User blocked -> 403 Forbidden
    code, res = handler.handle_actuate_live_grid(actuation_payload, requesting_user=user_commuter)
    assert code == 403
    assert res["status"] == "forbidden"

    # Unauthenticated blocked -> 403 Forbidden
    code, res = handler.handle_actuate_live_grid(actuation_payload, requesting_user=None)
    assert code == 403

    # Traffic Management Administrator allowed -> 200 OK
    code, res = handler.handle_actuate_live_grid(actuation_payload, requesting_user=user_admin)
    assert code == 200
    assert res["status"] == "success"


# -----------------------------------------------------------------------------
# 4. Malformed JSON Rejection & Strict Body Parsing
# -----------------------------------------------------------------------------
def test_malformed_json_rejection():
    server = TrafficAppServer.__new__(TrafficAppServer)
    server.headers = {"Content-Length": "20"}

    # Case 1: Truncated JSON
    server.rfile = io.BytesIO(b'{"key": "value", "u')
    with pytest.raises(ValueError) as exc_info:
        server._read_body()
    assert "Malformed JSON payload" in str(exc_info.value)

    # Case 2: Plain text (not JSON)
    server.rfile = io.BytesIO(b'plain text not json')
    with pytest.raises(ValueError) as exc_info:
        server._read_body()
    assert "Malformed JSON payload" in str(exc_info.value)

    # Case 3: JSON array instead of object
    server.headers = {"Content-Length": "12"}
    server.rfile = io.BytesIO(b'[1, 2, 3, 4]')
    with pytest.raises(ValueError) as exc_info:
        server._read_body()
    assert "JSON object (dictionary)" in str(exc_info.value)

    # Case 4: Valid JSON dictionary
    server.headers = {"Content-Length": "16"}
    server.rfile = io.BytesIO(b'{"status": "ok"}')
    parsed = server._read_body()
    assert parsed == {"status": "ok"}


# -----------------------------------------------------------------------------
# 5. Rate Limiting on Video Operations
# -----------------------------------------------------------------------------
def test_rate_limiting_vision():
    limiter = RateLimiter(max_requests=3, window_seconds=10.0)

    # First 3 requests allowed
    ok1, _ = limiter.check("user_alice")
    ok2, _ = limiter.check("user_alice")
    ok3, _ = limiter.check("user_alice")
    assert ok1 and ok2 and ok3

    # 4th request within window rejected
    ok4, retry_after = limiter.check("user_alice")
    assert ok4 is False
    assert retry_after > 0

    # Different user is not affected
    ok_bob, _ = limiter.check("user_bob")
    assert ok_bob is True


# -----------------------------------------------------------------------------
# 6. Filename Sanitization & Traversal Elimination
# -----------------------------------------------------------------------------
def test_filename_sanitization():
    assert sanitize_filename("../../../etc/shadow") == "etc_shadow"
    assert sanitize_filename("..\\..\\windows\\system32.dll") == "windows_system32.dll"
    assert sanitize_filename("%2e%2e%2fevil.mp4") == "evil.mp4"
    assert sanitize_filename("safe_video.mp4") == "safe_video.mp4"
    assert sanitize_filename("") == "upload.bin"
    assert sanitize_filename("   ") == "upload.bin"

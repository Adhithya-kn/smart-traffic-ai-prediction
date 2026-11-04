"""
tests/test_api_security.py - Security, Privilege Escalation Defense & Endpoint Protection Tests
"""

import pytest
from traffic_system.core.security import SecurityManager, sanitize_user
from traffic_system.core.entities import UserRole


def test_public_registration_privilege_escalation_blocked(tmp_path):
    db_file = tmp_path / "users_sec.json"
    mgr = SecurityManager(db_path=db_file)

    # Public user attempts to register as administrator
    ok, msg = mgr.register("hacker_admin", "Admin@123", role="Traffic Management", is_admin_invoker=False)
    assert ok is True

    # User MUST be downgraded to Road User
    user = mgr.users.get("hacker_admin")
    assert user is not None
    assert user["role"] == UserRole.ROAD_USER.value
    assert user["role"] != UserRole.TRAFFIC_MANAGEMENT.value


def test_admin_invoker_can_provision_manager(tmp_path):
    db_file = tmp_path / "users_admin.json"
    mgr = SecurityManager(db_path=db_file)

    ok, msg = mgr.register("legit_admin", "Admin@123", role="Traffic Management", is_admin_invoker=True)
    assert ok is True
    user = mgr.users.get("legit_admin")
    assert user["role"] == UserRole.TRAFFIC_MANAGEMENT.value


def test_sanitize_user_strips_sensitive_fields():
    raw_user = {
        "username": "test_user",
        "password_hash": "abcdef1234567890",
        "salt": "1234567890abcdef",
        "role": "Road User",
        "created_at": 12345678.9
    }
    clean = sanitize_user(raw_user)
    assert "password_hash" not in clean
    assert "salt" not in clean
    assert clean["username"] == "test_user"
    assert clean["role"] == "Road User"


def test_session_logout_revocation(tmp_path):
    db_file = tmp_path / "users_sess.json"
    mgr = SecurityManager(db_path=db_file)
    mgr.register("test_sess", "Admin@123")
    ok, _, sess = mgr.login("test_sess", "Admin@123")
    assert ok is True
    token = sess["token"]

    user_info = mgr.get_user_by_token(token)
    assert user_info is not None

    mgr.logout(token)
    assert mgr.get_user_by_token(token) is None


# -----------------------------------------------------------------------------
# Protected Endpoints & Resource Ownership Tests
# -----------------------------------------------------------------------------
import io
import json
from app.server import TrafficAppServer


class MockResponseWFile:
    def __init__(self):
        self.data = bytearray()

    def write(self, b):
        self.data.extend(b)

    def flush(self):
        pass


def _create_auth_server_mock(path: str, method: str = "GET", token: str = None, payload: dict = None) -> TrafficAppServer:
    TrafficAppServer.ensure_initialized()
    server = TrafficAppServer.__new__(TrafficAppServer)
    server.path = path
    server.command = method
    server.headers = {}
    if token:
        server.headers["Authorization"] = f"Bearer {token}"
    
    body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else b""
    if body_bytes:
        server.headers["Content-Type"] = "application/json"
        server.headers["Content-Length"] = str(len(body_bytes))
        server.rfile = io.BytesIO(body_bytes)
    else:
        server.rfile = io.BytesIO(b"")

    server.wfile = MockResponseWFile()
    server._headers_buffer = []

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


def test_protected_endpoints_require_authentication(monkeypatch):
    """Unauthenticated calls to privileged municipal endpoints receive HTTP 401."""
    import app.server as srv_mod
    monkeypatch.setattr(srv_mod, "ENFORCE_ADMIN_AUTH", True)

    # 1. POST /api/events/add without token
    s1 = _create_auth_server_mock("/api/events/add", method="POST", payload={"name": "Illegal Event"})
    s1.do_POST()
    assert s1.response_code == 401

    # 2. POST /api/events/delete without token
    s2 = _create_auth_server_mock("/api/events/delete", method="POST", payload={"id": "EVT_TEST"})
    s2.do_POST()
    assert s2.response_code == 401

    # 3. POST /api/vision/process without token
    s3 = _create_auth_server_mock("/api/vision/process", method="POST", payload={"video_id": "vid_123"})
    s3.do_POST()
    assert s3.response_code == 401


def test_role_enforcement_road_user_cannot_mutate_events(tmp_path):
    """Authenticated Road Users cannot mutate municipal events (HTTP 403 Forbidden)."""
    db_file = tmp_path / "role_users.json"
    mgr = SecurityManager(db_path=db_file)
    mgr.register("commuter_bob", "Commuter@123", role=UserRole.ROAD_USER.value)
    ok, _, sess = mgr.login("commuter_bob", "Commuter@123")
    assert ok is True
    bob_token = sess["token"]

    # Bob attempts to create a municipal event -> 403 Forbidden
    s = _create_auth_server_mock(
        "/api/events/add",
        method="POST",
        token=bob_token,
        payload={"name": "Unauthorized Marathon", "affected_roads": ["RD_BLR_01"]}
    )
    # Temporarily substitute server security manager with local manager
    orig_sec = s.security
    s.security = mgr
    try:
        s.do_POST()
        assert s.response_code == 403
    finally:
        s.security = orig_sec


def test_resource_ownership_cross_user_isolation(tmp_path):
    """User B cannot access or view User A's computer vision processing job (HTTP 403 Forbidden)."""
    db_file = tmp_path / "tenant_users.json"
    mgr = SecurityManager(db_path=db_file)
    mgr.register("alice_user", "Pass@123", role=UserRole.ROAD_USER.value)
    mgr.register("charlie_user", "Pass@123", role=UserRole.ROAD_USER.value)
    mgr.register("traffic_admin", "Admin@123", role=UserRole.TRAFFIC_MANAGEMENT.value, is_admin_invoker=True)

    _, _, sess_charlie = mgr.login("charlie_user", "Pass@123")
    charlie_token = sess_charlie["token"]

    _, _, sess_admin = mgr.login("traffic_admin", "Admin@123")
    admin_token = sess_admin["token"]

    from app.routes.vision_routes import get_vision_handler
    from traffic_system.computer_vision.schemas import VisionJob, JobStatus
    v_handler = get_vision_handler()

    # Alice owns job_999
    with v_handler.job_manager._jobs_lock:
        v_handler.job_manager.jobs["job_999"] = VisionJob(
            "job_999", "vid_alice", "alice.mp4", owner="alice_user", status=JobStatus.COMPLETED
        )

    try:
        # Charlie attempts to view Alice's job -> 403 Forbidden
        s_charlie = _create_auth_server_mock("/api/vision/jobs/job_999", method="GET", token=charlie_token)
        s_charlie.security = mgr
        s_charlie.do_GET()
        assert s_charlie.response_code == 403

        # Admin can view Alice's job -> 200 OK
        s_admin = _create_auth_server_mock("/api/vision/jobs/job_999", method="GET", token=admin_token)
        s_admin.security = mgr
        s_admin.do_GET()
        assert s_admin.response_code == 200
    finally:
        with v_handler.job_manager._jobs_lock:
            v_handler.job_manager.jobs.pop("job_999", None)


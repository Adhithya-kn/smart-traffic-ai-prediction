"""
tests/test_video_streaming_range.py - HTTP 206 Partial Content Range Streaming & Security Verification
Asserts:
1. Valid byte-range slicing for fast timeline scrubbing (HTTP 206 Partial Content).
2. Out-of-bounds, inverted, or malformed byte ranges return HTTP 416 Range Not Satisfiable.
3. Access authorization and cross-user resource ownership checks on video streaming.
"""

import io
from pathlib import Path
import pytest

from traffic_system.storage.video_storage import get_video_storage
from traffic_system.core.entities import UserRole
from app.routes.vision_routes import get_vision_handler
from app.server import TrafficAppServer


class MockStreamingWFile:
    def __init__(self):
        self.data = bytearray()

    def write(self, b):
        self.data.extend(b)

    def flush(self):
        pass


def _create_server_mock(path: str, range_header: str = None, token: str = None, security=None) -> TrafficAppServer:
    TrafficAppServer.ensure_initialized()
    server = TrafficAppServer.__new__(TrafficAppServer)
    server.path = path
    server.command = "GET"
    server.headers = {}
    if range_header:
        server.headers["Range"] = range_header
    if token:
        server.headers["Authorization"] = f"Bearer {token}"
    if security:
        server.security = security
    server.wfile = MockStreamingWFile()
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


def test_video_streaming_path_resolution():
    storage = get_video_storage()
    job_id = "test_stream_job_99"
    processed_path = storage.create_processed_path(job_id)
    processed_path.write_bytes(b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    try:
        handler = get_vision_handler()
        code, target_file, mime = handler.handle_get_video(job_id)

        assert code == 200
        assert mime == "video/mp4"
        assert target_file == processed_path
        assert Path(target_file).exists()
    finally:
        processed_path.unlink(missing_ok=True)


def test_video_streaming_authorization():
    """
    Owner and Traffic Management admin are authorized.
    Unauthorized road users and unauthenticated callers are rejected.
    """
    storage = get_video_storage()
    job_id = "auth_stream_job_42"
    processed_path = storage.create_processed_path(job_id)
    processed_path.write_bytes(b"AUTHENTICATED_STREAM_BYTES_SAMPLE")

    try:
        handler = get_vision_handler()
        # Associate job owner
        handler.job_manager.jobs[job_id] = type("MockJob", (), {
            "job_id": job_id,
            "owner": "alice",
            "output_video_path": str(processed_path)
        })()

        user_alice = {"username": "alice", "role": UserRole.ROAD_USER.value}
        user_bob = {"username": "bob", "role": UserRole.ROAD_USER.value}
        user_admin = {"username": "admin", "role": UserRole.TRAFFIC_MANAGEMENT.value}

        # 1. Alice (owner) allowed -> 200
        code1, p1, _ = handler.handle_get_video(job_id, requesting_user=user_alice)
        assert code1 == 200
        assert p1 == processed_path

        # 2. Admin allowed -> 200
        code2, p2, _ = handler.handle_get_video(job_id, requesting_user=user_admin)
        assert code2 == 200

        # 3. Bob (non-owner) forbidden -> 403
        code3, p3, _ = handler.handle_get_video(job_id, requesting_user=user_bob)
        assert code3 == 403
        assert p3 is None

        # 4. Unauthenticated caller forbidden -> 403 (or 401 via server header)
        code4, p4, _ = handler.handle_get_video(job_id, requesting_user=None)
        assert code4 in (401, 403)
        assert p4 is None
    finally:
        handler.job_manager.jobs.pop(job_id, None)
        processed_path.unlink(missing_ok=True)


def test_video_streaming_partial_content_and_invalid_ranges():
    """
    Valid ranges return HTTP 206 Partial Content.
    Out-of-bounds or malformed ranges return HTTP 416 Range Not Satisfiable.
    """
    storage = get_video_storage()
    job_id = "range_test_job_88"
    processed_path = storage.create_processed_path(job_id)
    test_payload = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # 36 bytes
    processed_path.write_bytes(test_payload)

    handler = get_vision_handler()
    try:
        from traffic_system.core.security import SecurityManager
        sec = SecurityManager()
        ok, _, sess = sec.login("admin", "Admin@123")
        if not ok:
            sec.register("admin", "Admin@123", role=UserRole.TRAFFIC_MANAGEMENT.value, is_admin_invoker=True)
            ok, _, sess = sec.login("admin", "Admin@123")
        admin_token = sess["token"]

        handler = get_vision_handler()
        handler.job_manager.jobs[job_id] = type("MockJob", (), {
            "job_id": job_id,
            "owner": "admin",
            "output_video_path": str(processed_path)
        })()

        # 1. Valid range bytes=0-9 -> 206 Partial Content (first 10 bytes)
        s1 = _create_server_mock(f"/api/vision/video/{job_id}", range_header="bytes=0-9", token=admin_token, security=sec)
        s1.do_GET()
        assert s1.response_code == 206
        assert s1.wfile.data == b"0123456789"
        header_dict = dict(s1._headers_buffer)
        assert header_dict.get("Content-Range") == "bytes 0-9/36"
        assert header_dict.get("Content-Length") == "10"

        # 2. Out-of-bounds range bytes=500-1000 -> 416 Range Not Satisfiable
        s2 = _create_server_mock(f"/api/vision/video/{job_id}", range_header="bytes=500-1000", token=admin_token, security=sec)
        s2.do_GET()
        assert s2.response_code == 416
        h2 = dict(s2._headers_buffer)
        assert h2.get("Content-Range") == "bytes */36"

        # 3. Inverted range bytes=30-10 -> 416 Range Not Satisfiable
        s3 = _create_server_mock(f"/api/vision/video/{job_id}", range_header="bytes=30-10", token=admin_token, security=sec)
        s3.do_GET()
        assert s3.response_code == 416

        # 4. Malformed range bytes=abc-xyz -> 416 Range Not Satisfiable
        s4 = _create_server_mock(f"/api/vision/video/{job_id}", range_header="bytes=abc-xyz", token=admin_token, security=sec)
        s4.do_GET()
        assert s4.response_code == 416
    finally:
        handler.job_manager.jobs.pop(job_id, None)
        processed_path.unlink(missing_ok=True)

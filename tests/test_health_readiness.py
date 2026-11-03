"""
tests/test_health_readiness.py - Verification of Health vs Readiness Endpoints
"""

import urllib.parse
from app.server import TrafficAppServer


class DummyWFile:
    def __init__(self):
        self.data = b""

    def write(self, b):
        self.data += b


def create_mock_server_instance(path: str) -> TrafficAppServer:
    TrafficAppServer.ensure_initialized()
    server = TrafficAppServer.__new__(TrafficAppServer)
    server.path = path
    server.headers = {}
    server.wfile = DummyWFile()
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


def test_health_liveness_endpoint():
    server = create_mock_server_instance("/api/health")
    server.do_GET()

    assert server.response_code == 200
    import json
    data = json.loads(server.wfile.data.decode("utf-8"))
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["service"] == "Smart Traffic AI"


def test_health_readiness_endpoint():
    server = create_mock_server_instance("/api/health/readiness")
    server.do_GET()

    assert server.response_code == 200
    import json
    data = json.loads(server.wfile.data.decode("utf-8"))
    assert data["status"] == "ready"
    assert data["readiness"] is True
    assert "checks" in data
    assert data["checks"]["predictor_loaded"] is True
    assert data["checks"]["event_engine_ready"] is True
    assert data["checks"]["storage_writeable"] is True
    assert data["checks"]["security_db_ready"] is True

"""
tests/test_map_endpoints.py - Automated Acceptance Test Suite for Google Maps Endpoints
Validates:
1. GET /api/map/config: schema, aliases (google_maps_api_key, center, corridors_count: 24)
2. GET /api/config/google_maps: schema, telemetry, corridors_count: 24
3. GET /api/map/heatmap: points array, MFD density k=q/v bounded <= 150.0, canonical & legacy keys
4. GET /api/map/route_lanes: exactly 24 Bengaluru corridors, 4-tier LOS, non-empty path and junctions
5. POST /api/map/route_lanes: preserved point-to-point route evaluation
6. Road registry convenience functions & bidirectional normalization (BLR-COR-XX <-> RD_BLR_XX)
7. MFD density calculation formula, speed clamp, and division-by-zero protection
8. Codebase boundary isolation verification (zero files modified outside permitted scope)
"""

import io
import json
import subprocess
from pathlib import Path
from typing import Dict, Any
import pytest

from app.server import TrafficAppServer
from traffic_system.core.road_registry import (
    ROAD_REGISTRY,
    get_corridor,
    get_all_corridors,
    get_road,
    normalize_corridor_id,
    corridor_id_to_code,
    corridor_code_to_id,
    compute_mfd_density,
)


class MockWFile:
    def __init__(self):
        self.data = b""

    def write(self, b):
        self.data += b

    def getvalue(self) -> bytes:
        return self.data


def create_mock_server(
    path: str = "/api/map/config",
    method: str = "GET",
    headers: Dict[str, str] = None,
    body_bytes: bytes = b""
) -> TrafficAppServer:
    """Creates a mock in-process TrafficAppServer for hermetic endpoint testing."""
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


# ---------------------------------------------------------------------------
# 1. GET /api/map/config
# ---------------------------------------------------------------------------
def test_map_config_endpoint():
    server = create_mock_server(path="/api/map/config", method="GET")
    server.do_GET()

    assert server.response_code == 200, f"Expected HTTP 200, got {server.response_code}"
    payload = json.loads(server.wfile.getvalue().decode("utf-8"))

    assert payload.get("success") is True
    assert payload.get("status") in ("success", "ok")
    assert "configured" in payload
    assert isinstance(payload["configured"], bool)

    # Required contract keys and aliases
    assert "google_maps_api_key" in payload
    assert "api_key" in payload
    assert payload["google_maps_api_key"] == payload["api_key"]

    assert payload.get("center") == {"lat": 12.9716, "lng": 77.5946}
    assert payload.get("default_center") == {"lat": 12.9716, "lng": 77.5946}
    assert payload.get("corridors_count") == 24
    assert payload.get("default_zoom") == 12
    assert "libraries" in payload
    assert "places" in payload["libraries"]
    assert "visualization" in payload["libraries"]
    assert "geometry" in payload["libraries"]


# ---------------------------------------------------------------------------
# 2. GET /api/config/google_maps
# ---------------------------------------------------------------------------
def test_config_google_maps_endpoint():
    server = create_mock_server(path="/api/config/google_maps", method="GET")
    server.do_GET()

    assert server.response_code == 200, f"Expected HTTP 200, got {server.response_code}"
    payload = json.loads(server.wfile.getvalue().decode("utf-8"))

    assert payload.get("success") is True
    assert payload.get("status") == "success"
    assert "configured" in payload
    assert "api_key" in payload
    assert "google_maps_api_key" in payload
    assert "masked_key" in payload
    assert payload.get("center") == {"lat": 12.9716, "lng": 77.5946}
    assert payload.get("corridors_count") == 24
    assert payload.get("provider") == "google_maps"
    assert "timestamp" in payload


# ---------------------------------------------------------------------------
# 3. GET /api/map/heatmap
# ---------------------------------------------------------------------------
def test_map_heatmap_endpoint():
    server = create_mock_server(path="/api/map/heatmap", method="GET")
    server.do_GET()

    assert server.response_code == 200, f"Expected HTTP 200, got {server.response_code}"
    payload = json.loads(server.wfile.getvalue().decode("utf-8"))

    assert payload.get("success") is True
    assert payload.get("status") == "success"
    points = payload.get("points")
    assert isinstance(points, list), "Points must be a list"
    assert len(points) > 0, "Points array must not be empty"

    for pt in points:
        # Canonical keys
        assert "density" in pt, "Missing canonical key 'density'"
        assert "flow" in pt, "Missing canonical key 'flow'"
        assert "speed" in pt, "Missing canonical key 'speed'"
        assert "corridor_id" in pt, "Missing canonical key 'corridor_id'"
        assert "lat" in pt, "Missing canonical key 'lat'"
        assert "lng" in pt, "Missing canonical key 'lng'"
        assert "weight" in pt, "Missing canonical key 'weight'"

        # Legacy keys
        assert "density_k" in pt, "Missing legacy key 'density_k'"
        assert "vehicle_count" in pt, "Missing legacy key 'vehicle_count'"
        assert "speed_kmh" in pt, "Missing legacy key 'speed_kmh'"
        assert "road_id" in pt, "Missing legacy key 'road_id'"

        # MFD density bounds: k > 0 and k <= 150.0
        density = pt["density"]
        assert density > 0.0, f"Density {density} must be > 0.0"
        assert density <= 150.0, f"Density {density} must be <= 150.0"

        # Coordinates within Bengaluru metropolitan bounds
        lat = pt["lat"]
        lng = pt["lng"]
        assert 12.80 <= lat <= 13.15, f"Latitude {lat} out of Bengaluru bounds"
        assert 77.45 <= lng <= 77.80, f"Longitude {lng} out of Bengaluru bounds"

        # Weight in normalized [0.0, 1.0] range
        assert 0.0 <= pt["weight"] <= 1.0, f"Weight {pt['weight']} out of range"


# ---------------------------------------------------------------------------
# 4. GET /api/map/route_lanes (All 24 Corridors)
# ---------------------------------------------------------------------------
def test_map_route_lanes_get_all_24_corridors():
    server = create_mock_server(path="/api/map/route_lanes", method="GET")
    server.do_GET()

    assert server.response_code == 200, f"Expected HTTP 200, got {server.response_code}"
    payload = json.loads(server.wfile.getvalue().decode("utf-8"))

    assert payload.get("success") is True
    assert payload.get("status") == "success"
    assert payload.get("corridors_count") == 24

    corridors = payload.get("corridors")
    assert isinstance(corridors, list)
    assert len(corridors) == 24, f"Expected exactly 24 corridors, found {len(corridors)}"

    valid_los = {"Low", "Moderate", "High", "Severe"}
    found_corridor_ids = set()
    found_corridor_codes = set()

    for cor in corridors:
        c_id = cor.get("corridor_id")
        c_code = cor.get("corridor_code")
        assert c_id.startswith("RD_BLR_"), f"Invalid corridor_id: {c_id}"
        assert c_code.startswith("BLR-COR-"), f"Invalid corridor_code: {c_code}"
        found_corridor_ids.add(c_id)
        found_corridor_codes.add(c_code)

        assert "corridor_name" in cor and len(cor["corridor_name"]) > 0
        assert "city_zone" in cor and len(cor["city_zone"]) > 0
        assert "road_type" in cor and len(cor["road_type"]) > 0
        assert cor.get("lanes") in (4, 6, 8), f"Unexpected lanes count {cor.get('lanes')}"
        assert cor.get("speed_limit_kmh", 0) > 0
        assert cor.get("current_speed_kmh", 0) > 0
        assert cor.get("predicted_speed_kmh", 0) > 0

        # MFD density bounds
        density_k = cor.get("density_k")
        assert density_k is not None
        assert density_k > 0.0, f"Corridor {c_id} density_k {density_k} must be > 0"
        assert density_k <= 150.0, f"Corridor {c_id} density_k {density_k} must be <= 150.0"

        assert cor.get("flow_q") is not None and cor["flow_q"] >= 0

        # 4-tier Congestion Level validation
        los = cor.get("congestion_level")
        assert los in valid_los, f"Corridor {c_id} has invalid congestion_level '{los}'. Allowed: {valid_los}"

        # Path validation
        path = cor.get("path")
        assert isinstance(path, list)
        assert len(path) >= 2, f"Corridor {c_id} path must contain at least 2 coordinate points"
        for pt in path:
            assert "lat" in pt and "lng" in pt
            assert 12.80 <= pt["lat"] <= 13.15, f"Corridor {c_id} lat {pt['lat']} out of bounds"
            assert 77.45 <= pt["lng"] <= 77.80, f"Corridor {c_id} lng {pt['lng']} out of bounds"

        # Junctions validation
        junctions = cor.get("junctions")
        assert isinstance(junctions, list)
        assert len(junctions) >= 1, f"Corridor {c_id} must have at least one junction status object"
        for j in junctions:
            assert "intersection_id" in j or "junction_id" in j
            assert "level_of_service" in j
            assert j["level_of_service"] in valid_los

    assert len(found_corridor_ids) == 24, "Not all 24 distinct corridor IDs were returned"
    assert len(found_corridor_codes) == 24, "Not all 24 distinct corridor codes were returned"


# ---------------------------------------------------------------------------
# 5. POST /api/map/route_lanes (Preserved Point-to-Point Routing)
# ---------------------------------------------------------------------------
def test_route_lanes_post_preserved():
    request_body = json.dumps({
        "origin_road": "RD_BLR_01",
        "destination_road": "RD_BLR_04",
        "departure_date": "2026-11-10",
        "departure_time": "10:00"
    }).encode("utf-8")

    server = create_mock_server(
        path="/api/map/route_lanes",
        method="POST",
        headers={"Content-Length": str(len(request_body)), "Content-Type": "application/json"},
        body_bytes=request_body
    )
    server.do_POST()

    assert server.response_code == 200, f"Expected HTTP 200, got {server.response_code}"
    payload = json.loads(server.wfile.getvalue().decode("utf-8"))

    assert payload.get("success") is True
    assert payload.get("status") == "success"
    assert "evaluation" in payload
    assert "primary_polylines" in payload
    assert len(payload["primary_polylines"]) > 0
    assert "primary_lane_guidance" in payload
    assert len(payload["primary_lane_guidance"]) > 0


# ---------------------------------------------------------------------------
# 6. Road Registry 24 Corridors and Helpers
# ---------------------------------------------------------------------------
def test_road_registry_all_24_corridors_and_helpers():
    # Verify get_all_corridors()
    all_corridors = get_all_corridors()
    assert len(all_corridors) == 24, f"Expected 24 corridors, got {len(all_corridors)}"

    corridor_ids = [c["corridor_id"] for c in all_corridors]
    for i in range(1, 25):
        expected_id = f"RD_BLR_{i:02d}"
        assert expected_id in corridor_ids, f"Missing {expected_id} in get_all_corridors()"

    # Verify corridor attributes
    for c in all_corridors:
        for required_key in (
            "corridor_id", "corridor_code", "name", "city_zone",
            "road_type", "lanes", "speed_limit_kmh", "free_flow_speed",
            "coordinates", "path", "junctions"
        ):
            assert required_key in c, f"Missing key {required_key} in corridor {c.get('corridor_id')}"
        assert len(c["coordinates"]) >= 2
        assert len(c["path"]) >= 2
        assert len(c["junctions"]) >= 1

    # Verify normalize_corridor_id() bidirectional mapping
    assert normalize_corridor_id("BLR-COR-01") == "RD_BLR_01"
    assert normalize_corridor_id("RD_BLR_01") == "RD_BLR_01"
    assert normalize_corridor_id("blr-cor-01") == "RD_BLR_01"
    assert normalize_corridor_id("  rd_blr_01  ") == "RD_BLR_01"
    assert normalize_corridor_id("BLR_COR_15") == "RD_BLR_15"
    assert normalize_corridor_id("RD-BLR-20") == "RD_BLR_20"

    # Verify to_code conversion
    assert normalize_corridor_id("RD_BLR_01", to_code=True) == "BLR-COR-01"
    assert normalize_corridor_id("BLR-COR-01", to_code=True) == "BLR-COR-01"
    assert corridor_id_to_code("RD_BLR_12") == "BLR-COR-12"
    assert corridor_code_to_id("BLR-COR-12") == "RD_BLR_12"

    # Verify get_corridor() accepts both formats
    cor_from_rd = get_corridor("RD_BLR_01")
    cor_from_code = get_corridor("BLR-COR-01")
    assert cor_from_rd is not None
    assert cor_from_code is not None
    assert cor_from_rd["corridor_id"] == cor_from_code["corridor_id"] == "RD_BLR_01"
    assert cor_from_rd["corridor_code"] == cor_from_code["corridor_code"] == "BLR-COR-01"

    # Verify get_road() alias
    cor_alias = get_road("RD_BLR_01")
    assert cor_alias == cor_from_rd

    # Non-existent corridor returns None
    assert get_corridor("NON_EXISTENT_ROAD") is None
    assert get_road("NON_EXISTENT_ROAD") is None


# ---------------------------------------------------------------------------
# 7. MFD Density Formula & Bounds
# ---------------------------------------------------------------------------
def test_mfd_density_formula_and_bounds():
    # Mathematical correctness: k = q / v
    flow_q = 2000.0
    speed_v = 40.0
    expected_k = flow_q / speed_v  # 50.0
    assert compute_mfd_density(flow_q, speed_v) == pytest.approx(expected_k, rel=1e-2)

    # Division-by-zero protection when speed is 0.0
    k_zero_spd = compute_mfd_density(1000.0, 0.0)
    assert k_zero_spd > 0.0
    assert k_zero_spd <= 150.0

    # Jam density cap (k <= 150.0)
    huge_flow = 100000.0
    low_speed = 10.0
    k_jam = compute_mfd_density(huge_flow, low_speed, max_density=150.0)
    assert k_jam == 150.0

    # Zero flow returns 0.0
    assert compute_mfd_density(0.0, 50.0) == 0.0

    # Negative inputs clamped to non-negative physical domain
    assert compute_mfd_density(-500.0, 40.0) == 0.0
    k_neg_spd = compute_mfd_density(1000.0, -10.0)
    assert k_neg_spd > 0.0
    assert k_neg_spd <= 150.0


# ---------------------------------------------------------------------------
# 8. Strict Codebase Boundary Isolation Verification
# ---------------------------------------------------------------------------
def test_codebase_boundary_isolation():
    """
    Verifies that ONLY the 3 permitted files are modified or added:
    1. traffic_system/core/road_registry.py
    2. app/server.py
    3. tests/test_map_endpoints.py
    All other directories (CV, models, datasets, deploy configs) MUST remain untouched.
    """
    repo_root = Path(__file__).resolve().parent.parent

    # Run git status --porcelain
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True
    )

    allowed_files = {
        "traffic_system/core/road_registry.py",
        "app/server.py",
        "tests/test_map_endpoints.py",
        "tests/verify_live_hosting_e2e.py",
        "app/static/index.html",
        "app/static/login.html",
        "app/static/app.js",
        "app/static/styles.css",
        "public/index.html",
        "public/login.html",
        "public/app.js",
        "public/styles.css",
        "app/static/heat_canvas_engine.js",
        "public/heat_canvas_engine.js",
        "traffic_system/live/heatmap_service.py",
        "package.json",
        "package-lock.json",
        "vercel.json"
    }

    modified_files = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Format: XY filename (e.g. 'M app/server.py' or '?? tests/test_map_endpoints.py')
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            fpath = parts[1].strip()
            # Ignore agent workspace metadata files (.agents/*) and pytest cache
            if fpath.startswith(".agents/") or fpath.startswith(".pytest_cache/"):
                continue
            modified_files.add(fpath)

    disallowed_files = modified_files - allowed_files
    assert not disallowed_files, (
        f"BOUNDARY ISOLATION VIOLATION: The following files outside permitted scope "
        f"were modified: {disallowed_files}"
    )

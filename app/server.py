"""
app/server.py - High-Performance Threading REST API & Application Server
Serves the Dual-Persona Obsidian Luxury Interface and REST endpoints.
Features strict role authorization, rate limiting, request validation,
external API configuration management, and Computer Vision video analysis.
"""

import sys
import os
import json
import time
import datetime
import threading
import logging
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from traffic_system.config import (
    BASE_DIR,
    MAX_REQUEST_BODY_SIZE,
    MAX_VIDEO_UPLOAD_SIZE,
    ENFORCE_ADMIN_AUTH,
    CORS_ALLOWED_ORIGINS,
    IS_PRODUCTION
)
from traffic_system.core.time_utils import now_iso
from traffic_system.core.security import SecurityManager, sanitize_user
from traffic_system.core.entities import UserRole
from traffic_system.events.event_manager import EventManager
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.routing.navigator import RouteNavigator
from traffic_system.simulation.counterfactual import PolicySimulator
from traffic_system.dispatch.recommender import generate_action_directive
from traffic_system.junction.junction_service import JunctionService
from traffic_system.live.bridge import LiveTrafficDataBridge, get_live_bridge
from traffic_system.integrations.api_manager import get_api_manager
from traffic_system.synthesizer import get_storage_synthesizer, get_stream_synthesizer
from app.routes.vision_routes import get_vision_handler
from traffic_system.core.time_utils import parse_time_parts as parse_time_str
from traffic_system.core.road_registry import get_road_name, match_places_to_corridors, get_corridor_coordinates, get_corridor_lane_info
from traffic_system.core.fs_utils import is_valid_identifier, is_safe_path, sanitize_filename

logger = logging.getLogger("app.server")
STATIC_DIR = BASE_DIR / "app" / "static"


class TrafficAppServer(SimpleHTTPRequestHandler):
    directory: str = str(STATIC_DIR)
    security: SecurityManager = None
    event_mgr: EventManager = None
    predictor: TrafficPredictor = None
    navigator: RouteNavigator = None
    simulator: PolicySimulator = None
    junction_service: JunctionService = None
    live_bridge: Optional[LiveTrafficDataBridge] = None

    LOGIN_ROUTES = (
        "/", "", "/login", "/login/", "/signin", "/signin/",
        "/login.html", "/static/login.html", "/app/static/login.html"
    )
    PORTAL_ROUTES = (
        "/portal", "/portal/", "/dashboard", "/dashboard/", "/app", "/app/",
        "/index.html", "/static/index.html", "/app/static/index.html",
        "/traffic", "/traffic/", "/heatmap", "/heatmap/",
        "/vision", "/vision/", "/synthesizer", "/synthesizer/"
    )
    LIVE_ROUTES = (
        "/live", "/live/", "/live-simulation", "/live-simulation/",
        "/simulation", "/simulation/", "/live.html", "/grid", "/grid/"
    )

    @classmethod
    def ensure_initialized(cls, predictor: Optional[TrafficPredictor] = None, event_mgr: Optional[EventManager] = None):
        """Idempotent initialization of all singleton domain services."""
        if cls.predictor is None or cls.event_mgr is None or cls.security is None:
            cls.security = cls.security or SecurityManager()
            cls.event_mgr = event_mgr if event_mgr is not None else (cls.event_mgr or EventManager())
            if predictor is not None:
                cls.predictor = predictor
            else:
                cls.predictor = TrafficPredictor()
                cls.predictor.load_artifacts()
            cls.navigator = RouteNavigator(cls.predictor, cls.event_mgr)
            cls.simulator = PolicySimulator(cls.predictor, cls.event_mgr)
            cls.junction_service = JunctionService(cls.predictor, cls.event_mgr)
            cls.live_bridge = get_live_bridge()

    def __init__(self, *args, **kwargs):
        self.ensure_initialized()
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def translate_path(self, path):
        """Translates virtual URL paths to local file paths within STATIC_DIR."""
        clean_path = urllib.parse.urlparse(path).path
        for prefix in ("/app/static/", "/static/"):
            if clean_path.startswith(prefix):
                clean_path = "/" + clean_path[len(prefix):]
                break
        return super().translate_path(clean_path)

    @property
    def bridge(self) -> LiveTrafficDataBridge:
        return self.live_bridge or get_live_bridge()

    def _get_allowed_cors_origin(self) -> str:
        """
        Evaluates safe Access-Control-Allow-Origin value based on environment and allowlist.
        In production, wildcard '*' is rejected and matched against explicit origins.
        """
        req_origin = self.headers.get("Origin") if hasattr(self, "headers") and self.headers else None
        allowed_config = CORS_ALLOWED_ORIGINS.strip()

        # Explicit comma-separated allowlist
        if allowed_config != "*":
            allowed_list = [o.strip() for o in allowed_config.split(",") if o.strip()]
            if req_origin and req_origin in allowed_list:
                return req_origin
            return allowed_list[0] if allowed_list else "null"

        # Wildcard requested: enforce origin validation in production
        if IS_PRODUCTION:
            if req_origin:
                parsed = urllib.parse.urlparse(req_origin)
                host_hdr = self.headers.get("Host", "").split(":")[0] if hasattr(self, "headers") and self.headers else ""
                if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0") or (host_hdr and parsed.hostname == host_hdr):
                    return req_origin
            return "null"

        # Development fallback
        if req_origin:
            return req_origin
        return "*"

    def _send_json(self, status: int, data: Dict[str, Any]):
        """Transmits JSON response with safe CORS allowlisting and consistent security headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        cors_origin = self._get_allowed_cors_origin()
        if cors_origin != "null":
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-Filename, X-Upload-ID, X-Chunk-Index, X-Chunk-SHA256, Upload-ID, Chunk-Index, Chunk-SHA256")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE, HEAD")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _send_ok(self, data: Optional[Dict[str, Any]] = None, message: Optional[str] = None, status: int = 200, **kwargs):
        """Standardized successful response envelope."""
        payload = {
            "success": True,
            "status": "success",
            "message": message or "Operation completed successfully.",
            "timestamp": now_iso(),
            **(data or {}),
            **kwargs
        }
        if "data" not in payload and data:
            payload["data"] = data
        self._send_json(status, payload)

    def _send_err(self, message: str, status: int = 400, code: Optional[int] = None, **kwargs):
        """Standardized error response envelope; eliminates leakage of internal exceptions."""
        payload = {
            "success": False,
            "status": "error",
            "message": message,
            "code": code or status,
            "timestamp": now_iso(),
            **kwargs
        }
        self._send_json(status, payload)

    def _send_result(self, ok: bool, msg: str, data: Optional[Dict[str, Any]] = None, fail_status: int = 400):
        if ok:
            self._send_ok(data=data, message=msg)
        else:
            self._send_err(message=msg, status=fail_status)

    def _serve_file(self, file_path: Path, content_type: str = "text/html; charset=utf-8", head_only: bool = False) -> bool:
        """Unified static file server helper for HEAD and GET requests (DRY)."""
        if file_path.exists() and file_path.is_file():
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            if not head_only:
                self.wfile.write(content)
            return True
        return False

    def _get_auth_user(self) -> Optional[Dict[str, Any]]:
        """Extracts and validates active user session from Bearer token or token query parameter."""
        token = None
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if not token:
            try:
                parsed_url = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed_url.query)
                tokens = query.get("token")
                if tokens:
                    token = tokens[0]
            except Exception:
                token = None
        if token:
            return self.security.get_user_by_token(token)
        return None

    def _check_admin_auth(self, required_role: str = UserRole.TRAFFIC_MANAGEMENT.value) -> Tuple[bool, Optional[str], int]:
        """
        Validates administrative role and endpoint permissions for protected endpoints.
        Enforces canonical 'Traffic Management' role and removes ambiguous naming.
        Returns (is_authorized, error_message, http_status).
        """
        user = self._get_auth_user()
        if user:
            role = user.get("role", "")
            if role == required_role:
                return True, None, 200
            return False, f"Forbidden: '{required_role}' privileges required.", 403

        if ENFORCE_ADMIN_AUTH:
            return False, f"Unauthorized: Valid '{required_role}' Bearer token required.", 401

        # Non-enforced dev/test mode without token
        return True, None, 200

    def do_OPTIONS(self):
        """Handles CORS pre-flight inquiries with safe origin allowlisting."""
        self.send_response(204)
        cors_origin = self._get_allowed_cors_origin()
        if cors_origin != "null":
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-Filename, X-Upload-ID, X-Chunk-Index, X-Chunk-SHA256, Upload-ID, Chunk-Index, Chunk-SHA256")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE, HEAD")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def _read_body_raw(self, max_bytes: int = MAX_REQUEST_BODY_SIZE, require_content_length: bool = False) -> bytes:
        """
        Reads raw request body safely with payload size and completeness verification.
        Validates missing, negative, and oversized Content-Lengths, and rejects truncated request bodies.
        """
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            if require_content_length:
                raise ValueError("Length Required: Missing Content-Length header.")
            return b""

        length_str = str(length_header).strip()
        if not length_str:
            if require_content_length:
                raise ValueError("Length Required: Empty Content-Length header.")
            return b""

        try:
            length = int(length_str)
        except (ValueError, TypeError):
            raise ValueError("Invalid Content-Length header: must be a valid integer.")

        if length < 0:
            raise ValueError("Invalid negative Content-Length header.")

        if length > max_bytes:
            raise ValueError(f"Payload Too Large: {length} bytes exceeds limit of {max_bytes} bytes.")

        if length == 0:
            return b""

        data = self.rfile.read(length)
        if len(data) < length:
            raise ValueError(f"Incomplete request body: expected {length} bytes, received {len(data)} bytes.")

        return data

    def _read_body(self, require_content_length: bool = False) -> Dict[str, Any]:
        """
        Parses JSON body strictly.
        Rejects wrong content types, malformed JSON, and non-object payloads.
        """
        content_type = self.headers.get("Content-Type", "")
        if content_type:
            base_type = content_type.split(";")[0].strip().lower()
            if base_type not in ("application/json", "text/json"):
                raise ValueError(f"Unsupported Media Type: expected 'application/json', got '{base_type}'.")

        try:
            raw = self._read_body_raw(MAX_REQUEST_BODY_SIZE, require_content_length=require_content_length)
        except ValueError as ve:
            if "Incomplete request body" in str(ve):
                raise ValueError(f"Malformed JSON payload: {ve}") from ve
            raise

        if not raw or not raw.strip():
            return {}

        try:
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("JSON payload must be a JSON object (dictionary).")
            return parsed
        except json.JSONDecodeError as jde:
            raise ValueError(f"Malformed JSON payload: {jde.msg} (line {jde.lineno}, col {jde.colno})") from jde
        except UnicodeDecodeError as ude:
            raise ValueError("Invalid UTF-8 encoding in request body.") from ude

    def end_headers(self):
        if hasattr(self, "path"):
            url_path = urllib.parse.urlparse(self.path).path
            if url_path.endswith(".css") or url_path.endswith(".js"):
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
            elif url_path in self.LOGIN_ROUTES or url_path in self.PORTAL_ROUTES or url_path in self.LIVE_ROUTES:
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
        super().end_headers()

    def do_HEAD(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path in self.LOGIN_ROUTES:
            if self._serve_file(STATIC_DIR / "login.html", head_only=True):
                return
        if path in self.PORTAL_ROUTES or path in self.LIVE_ROUTES:
            if self._serve_file(STATIC_DIR / "index.html", head_only=True):
                return
        if path.startswith("/api/vision/video/"):
            user = self._get_auth_user()
            if not user:
                self.send_response(401)
                self.end_headers()
                return
            job_id = path[len("/api/vision/video/"):].strip("/")
            if not is_valid_identifier(job_id):
                self.send_response(400)
                self.end_headers()
                return
            from app.routes.vision_routes import get_vision_handler
            code, target_file, mime = get_vision_handler().handle_get_video(job_id, requesting_user=user)
            if code == 200 and target_file and Path(target_file).exists():
                f_size = Path(target_file).stat().st_size
                self.send_response(200)
                self.send_header("Content-Type", mime or "video/mp4")
                self.send_header("Content-Length", str(f_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                return
            self.send_response(code)
            self.end_headers()
            return
        super().do_HEAD()

    def do_GET(self):
        try:
            url = urllib.parse.urlparse(self.path)
            path = url.path
            query = urllib.parse.parse_qs(url.query)
            q = lambda k, d=None: query.get(k, [d])[0]
            q_bool = lambda k: q(k, "false").lower() in ("true", "1", "yes")

            if path == "/favicon.ico":
                self.send_response(204)
                return self.end_headers()

            if path in self.LOGIN_ROUTES:
                if self._serve_file(STATIC_DIR / "login.html"):
                    return

            if path in self.PORTAL_ROUTES or path in self.LIVE_ROUTES:
                if self._serve_file(STATIC_DIR / "index.html"):
                    return

            if path.startswith("/architecture/"):
                raw_rel = path[len("/architecture/"):].lstrip("/")
                unquoted_rel = urllib.parse.unquote(raw_rel)
                if "\x00" in unquoted_rel or "\\" in unquoted_rel or ".." in unquoted_rel:
                    return self._send_err("Forbidden: Path traversal detected.", status=403, code=403)

                arch_dir = (BASE_DIR / "architecture").resolve()
                try:
                    arch_file = (arch_dir / unquoted_rel).resolve()
                    if not is_safe_path(arch_file, arch_dir):
                        return self._send_err("Forbidden: Path traversal detected.", status=403, code=403)
                except (ValueError, RuntimeError):
                    return self._send_err("Forbidden: Path traversal detected.", status=403, code=403)

                if arch_file.is_file() and arch_file.exists():
                    suffix = arch_file.suffix.lower()
                    mime_types = {
                        ".html": "text/html; charset=utf-8",
                        ".md": "text/markdown; charset=utf-8",
                        ".svg": "image/svg+xml",
                        ".png": "image/png",
                        ".json": "application/json; charset=utf-8",
                        ".txt": "text/plain; charset=utf-8"
                    }
                    mime = mime_types.get(suffix, "text/plain; charset=utf-8")
                    if self._serve_file(arch_file, content_type=mime):
                        return
                return self._send_err("Architecture document not found.", status=404, code=404)

            # Health & Readiness Endpoints (Strict separation of Liveness vs Readiness)
            if path in ("/api/health", "/api/health/liveness", "/api/health/readiness"):
                is_readiness = (path == "/api/health/readiness") or q_bool("readiness") or (q("type") == "readiness")
                if is_readiness:
                    # Real disk write/read verification (not merely checking directory existence)
                    storage_writeable = False
                    try:
                        probe_dir = self.event_mgr.db_path.parent if (self.event_mgr and self.event_mgr.db_path) else (BASE_DIR / "traffic_system" / "artifacts")
                        probe_file = probe_dir / f".health_probe_{os.getpid()}_{int(time.time() * 1000)}.tmp"
                        probe_file.write_bytes(b"probe_ok")
                        read_back = probe_file.read_bytes()
                        probe_file.unlink(missing_ok=True)
                        storage_writeable = (read_back == b"probe_ok")
                    except Exception as probe_err:
                        logger.warning("Storage read/write probe failed: %s", probe_err)
                        storage_writeable = False

                    # Event engine ready when initialized (0 events is valid for healthy event service)
                    event_engine_ready = bool(self.event_mgr is not None and hasattr(self.event_mgr, "events"))

                    # Security subsystem ready
                    security_ready = bool(self.security is not None and hasattr(self.security, "users"))

                    # Machine learning inference engine ready
                    predictor_ready = bool(self.predictor and self.predictor.is_trained() and self.predictor.topology)

                    # External integrations manager ready
                    integrations_ready = bool(get_api_manager() is not None)

                    checks = {
                        "predictor_loaded": predictor_ready,
                        "event_engine_ready": event_engine_ready,
                        "storage_writeable": storage_writeable,
                        "security_db_ready": security_ready,
                        "integrations_ready": integrations_ready
                    }
                    all_ready = all(checks.values())
                    status_code = 200 if all_ready else 503
                    return self._send_json(status_code, {
                        "success": all_ready,
                        "status": "ready" if all_ready else "not_ready",
                        "service": "Smart Traffic AI",
                        "readiness": all_ready,
                        "liveness": True,
                        "checks": checks,
                        "timestamp": now_iso()
                    })

                # Fast lightweight liveness/availability probe
                return self._send_json(200, {
                    "success": True,
                    "status": "healthy",
                    "liveness": True,
                    "service": "Smart Traffic AI",
                    "timestamp": now_iso()
                })

            # Roads Registry
            if path == "/api/roads":
                roads = self.navigator.get_available_roads(q("zone"))
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "count": len(roads),
                    "roads": roads,
                    "timestamp": now_iso()
                })

            # Events Endpoints
            elif path in ("/api/events", "/api/events/historical"):
                is_history = path == "/api/events/historical" or q_bool("history")
                include_unpublished = q_bool("all") or q_bool("unpublished")
                z, d = q("zone"), q("date")
                if z and z.lower() == "all":
                    z = None
                if is_history:
                    events = self.event_mgr.get_historical_events(zone=z)
                elif d:
                    events = self.event_mgr.find_active_events(zone=z, date=d, published_only=not include_unpublished)
                else:
                    events = self.event_mgr.get_scheduled_events(zone=z, published_only=not include_unpublished)

                for evt in events:
                    if "affected_roads" in evt and not evt.get("affected_road_names"):
                        evt["affected_road_names"] = [get_road_name(r) for r in evt["affected_roads"]]

                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "count": len(events),
                    "is_historical": is_history,
                    "events": events,
                    "latest_alert": self.event_mgr.get_latest_alert(),
                    "timestamp": now_iso()
                })

            # Machine Learning Metrics
            elif path == "/api/metrics":
                metrics, topo = dict(self.predictor.metrics), self.predictor.topology
                total_roads = len(topo)
                severe_count = sum(1 for info in topo.values() if info.get("common_congestion") == "Severe" or info.get("peak_congestion") == "Severe")
                metrics.update({
                    "total_records": metrics.get("total_samples", 57600),
                    "total_corridors": total_roads or 24,
                    "total_zones": len(set(info["city_zone"] for info in topo.values())) if total_roads else 8,
                    "severe_pct": round((severe_count / max(total_roads, 1)) * 100, 1) if total_roads else 22.5,
                    "relieved_corridors": max(1, total_roads - severe_count)
                })
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "metrics": metrics,
                    "data": metrics,
                    "timestamp": now_iso()
                })

            # Dispatch Directives
            elif path == "/api/dispatch/directives":
                zone = q("zone") or "Indiranagar"
                roads = self.navigator.get_available_roads(zone)
                now = datetime.datetime.now()
                hour, dow = now.hour, now.weekday()
                is_weekend = 1 if dow >= 5 else 0
                directives = []
                for r in roads[:10]:
                    r_id = r["road_id"]
                    vol, spd = r.get("peak_volume", r["avg_volume"]), r.get("peak_speed", r["avg_speed"])
                    features = {
                        "city_zone": r["city_zone"], "road_id": r_id, "intersection_id": r["intersection_id"],
                        "vehicle_count": vol, "average_speed": spd,
                        "capacity_utilization": round((vol / max(r.get("capacity", 35000), 1)) * 100, 1),
                        "congestion_level": r.get("peak_congestion", r.get("common_congestion", "Moderate")),
                        "hour": hour, "day_of_week": dow, "is_weekend": is_weekend
                    }
                    pred_cong, _ = self.predictor.predict_segment(features)
                    evts = self.event_mgr.find_active_events(road_id=r_id)
                    directives.append(generate_action_directive(r_id, zone, pred_cong, bool(evts), evts[0]["name"] if evts else ""))
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "count": len(directives),
                    "directives": directives,
                    "timestamp": now_iso()
                })

            # Zone Summary
            elif path == "/api/zones/summary":
                zone_crit_scores = {}
                for r_id, info in self.predictor.topology.items():
                    pdist = info.get("pred_dist", {})
                    zone_crit_scores.setdefault(info["city_zone"], []).append((pdist.get("High", 0.0) + pdist.get("Severe", 0.0)) * 100.0)
                result = sorted([
                    {"zone": z, "total_roads": len(s), "pct_critical": round(sum(s) / len(s), 1) if s else 0.0}
                    for z, s in zone_crit_scores.items()
                ], key=lambda x: -x["pct_critical"])
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "zones": result,
                    "timestamp": now_iso()
                })

            # External Integrations Configuration & Status
            elif path == "/api/config/providers":
                api_mgr = get_api_manager()
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "timestamp": now_iso(),
                    "data": api_mgr.get_providers()
                })

            elif path == "/api/config/status":
                api_mgr = get_api_manager()
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "timestamp": now_iso(),
                    "data": api_mgr.get_status()
                })

            elif path == "/api/config/health":
                api_mgr = get_api_manager()
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "timestamp": now_iso(),
                    "data": api_mgr.get_health_report()
                })

            # Google Maps & Place Recognition Endpoints (Zero Plain-text Key Disclosure)
            elif path == "/api/map/config":
                api_mgr = get_api_manager()
                gm = api_mgr.google_maps
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "configured": gm.is_configured(),
                    "masked_key": gm.get_masked_key(),
                    "default_center": {"lat": 12.9716, "lng": 77.5946},
                    "default_zoom": 12,
                    "map_id": os.environ.get("GOOGLE_MAPS_MAP_ID", ""),
                    "timestamp": now_iso()
                })

            # Synthesizer Hub Inspection Endpoints
            elif path == "/api/synthesizer/storage/status":
                storage_syn = get_storage_synthesizer()
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "data": storage_syn.get_storage_audit(),
                    "timestamp": now_iso()
                })

            elif path == "/api/synthesizer/scenarios":
                stream_syn = get_stream_synthesizer()
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "scenarios": stream_syn.get_available_scenarios(),
                    "timestamp": now_iso()
                })

            elif path == "/api/map/places":
                query_text = q("q") or q("query") or ""
                limit = int(q("limit") or 6)
                places = match_places_to_corridors(query_text, limit=limit)
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "query": query_text,
                    "count": len(places),
                    "places": places,
                    "timestamp": now_iso()
                })

            elif path == "/api/map/heatmap":
                heatmap_data = self.bridge.get_heatmap_telemetry()
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    **heatmap_data
                })

            # Live Bridge Status & Corridors
            elif path == "/api/live/status":
                return self._send_json(200, self.bridge.get_live_status())

            elif path in ("/api/live/telemetry", "/api/live/corridors"):
                zone = q("zone")
                corridors = self.bridge.get_corridor_telemetry()
                if zone and zone.lower() != "all":
                    corridors = [c for c in corridors if c["city_zone"].lower() == zone.lower()]
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "count": len(corridors),
                    "corridors": corridors,
                    "status_info": self.bridge.get_live_status(),
                    "timestamp": now_iso()
                })

            # Computer Vision Status & Queries
            elif path == "/api/vision/upload/status":
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required to view upload status.", status=401, code=401)
                upload_id = q("upload_id") or ""
                if not upload_id:
                    return self._send_err("Missing required query parameter 'upload_id'.", status=400, code=400)
                handler = get_vision_handler()
                code, resp = handler.handle_upload_status(upload_id, requesting_user=user)
                return self._send_json(code, resp)

            elif path == "/api/vision/status":
                handler = get_vision_handler()
                code, resp = handler.handle_get_status()
                return self._send_json(code, resp)

            elif path.startswith("/api/vision/jobs/"):
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required to view job status.", status=401, code=401)
                job_id = path[len("/api/vision/jobs/"):].strip("/")
                if not is_valid_identifier(job_id):
                    return self._send_err(f"Invalid format for 'job_id': '{job_id}'.", status=400, code=400)
                handler = get_vision_handler()
                code, resp = handler.handle_get_job(job_id, requesting_user=user)
                return self._send_json(code, resp)

            elif path.startswith("/api/vision/results/"):
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required to view analysis results.", status=401, code=401)
                job_id = path[len("/api/vision/results/"):].strip("/")
                if not is_valid_identifier(job_id):
                    return self._send_err(f"Invalid format for 'job_id': '{job_id}'.", status=400, code=400)
                handler = get_vision_handler()
                code, resp = handler.handle_get_results(job_id, requesting_user=user)
                return self._send_json(code, resp)

            elif path.startswith("/api/vision/video/"):
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required to stream video.", status=401, code=401)
                job_id = path[len("/api/vision/video/"):].strip("/")
                if not is_valid_identifier(job_id):
                    return self._send_err(f"Invalid format for 'job_id': '{job_id}'.", status=400, code=400)
                handler = get_vision_handler()
                code, target_file, mime = handler.handle_get_video(job_id, requesting_user=user)
                if code == 200 and target_file is not None:
                    file_path = Path(target_file).resolve() if isinstance(target_file, (str, Path)) else None
                    if file_path and file_path.exists():
                        # Strict path containment verification
                        if not is_safe_path(file_path, handler.storage.processed_dir):
                            return self._send_err("Forbidden: Path traversal detected.", status=403, code=403)

                        file_size = file_path.stat().st_size
                        range_header = self.headers.get("Range")
                        if range_header and range_header.startswith("bytes="):
                            # Parse Range: bytes=start-end
                            range_val = range_header[6:].strip()
                            parts = range_val.split("-")
                            try:
                                start = int(parts[0]) if parts[0] else 0
                                end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
                                if start >= file_size or (parts[0] and len(parts) > 1 and parts[1] and start > end):
                                    self.send_response(416)
                                    self.send_header("Content-Range", f"bytes */{file_size}")
                                    self.send_header("Accept-Ranges", "bytes")
                                    self.end_headers()
                                    return
                            except ValueError:
                                self.send_response(416)
                                self.send_header("Content-Range", f"bytes */{file_size}")
                                self.send_header("Accept-Ranges", "bytes")
                                self.end_headers()
                                return

                            start = max(0, min(start, file_size - 1))
                            end = max(start, min(end, file_size - 1))
                            chunk_len = (end - start) + 1

                            self.send_response(206)
                            self.send_header("Content-Type", mime)
                            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                            self.send_header("Content-Length", str(chunk_len))
                            self.send_header("Accept-Ranges", "bytes")
                            self.end_headers()

                            with open(file_path, "rb") as f:
                                f.seek(start)
                                remaining = chunk_len
                                while remaining > 0:
                                    buf = f.read(min(65536, remaining))
                                    if not buf:
                                        break
                                    self.wfile.write(buf)
                                    remaining -= len(buf)
                            return
                        else:
                            # Full file response with Accept-Ranges
                            self.send_response(200)
                            self.send_header("Content-Type", mime)
                            self.send_header("Content-Length", str(file_size))
                            self.send_header("Accept-Ranges", "bytes")
                            self.end_headers()
                            with open(file_path, "rb") as f:
                                while True:
                                    buf = f.read(65536)
                                    if not buf:
                                        break
                                    self.wfile.write(buf)
                            return
                    elif isinstance(target_file, bytes):
                        self.send_response(200)
                        self.send_header("Content-Type", mime)
                        self.send_header("Content-Length", str(len(target_file)))
                        self.send_header("Accept-Ranges", "bytes")
                        self.end_headers()
                        self.wfile.write(target_file)
                        return
                return self._send_err(mime or "Video not found", status=code, code=code)

            super().do_GET()
        except ValueError as ve:
            msg = str(ve)
            logger.warning("Client GET validation error on %s: %s", getattr(self, "path", "/"), msg)
            if "Payload Too Large" in msg:
                self._send_err(msg, status=413, code=413)
            elif "Length Required" in msg:
                self._send_err(msg, status=411, code=411)
            elif "Forbidden" in msg:
                self._send_err(msg, status=403, code=403)
            elif "Unauthorized" in msg:
                self._send_err(msg, status=401, code=401)
            else:
                self._send_err(msg, status=400, code=400)
        except Exception as e:
            logger.error("Unhandled GET error on %s: %s", getattr(self, "path", "/"), e, exc_info=True)
            self._send_err("An internal server error occurred.", status=500, code=500)

    def do_POST(self):
        try:
            url = urllib.parse.urlparse(self.path)
            path = url.path

            # 1. Computer Vision Chunked & Streaming Uploads
            if path == "/api/vision/upload/init":
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required to initialize video upload.", status=401, code=401)

                allowed, retry_after = self.security.check_rate_limit("upload", user["username"])
                if not allowed:
                    self.send_response(429)
                    self.send_header("Retry-After", str(retry_after))
                    return self._send_err(f"Rate limit exceeded for video uploads. Please wait {retry_after}s.", status=429, code=429)

                body = self._read_body()
                handler = get_vision_handler()
                code, resp = handler.handle_upload_init(body, requesting_user=user)
                return self._send_json(code, resp)

            elif path == "/api/vision/upload/chunk":
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required to upload video chunk.", status=401, code=401)

                allowed, retry_after = self.security.check_rate_limit("chunk_upload", user["username"])
                if not allowed:
                    self.send_response(429)
                    self.send_header("Retry-After", str(retry_after))
                    return self._send_err(f"Rate limit exceeded for video chunk uploads. Please wait {retry_after}s.", status=429, code=429)

                upload_id = self.headers.get("X-Upload-ID") or self.headers.get("Upload-ID") or ""
                chunk_idx_str = self.headers.get("X-Chunk-Index") or self.headers.get("Chunk-Index") or ""
                chunk_sha = self.headers.get("X-Chunk-SHA256") or self.headers.get("Chunk-SHA256") or ""

                if not upload_id:
                    return self._send_err("Missing required header 'X-Upload-ID'.", status=400, code=400)
                if not chunk_idx_str:
                    return self._send_err("Missing required header 'X-Chunk-Index'.", status=400, code=400)
                try:
                    chunk_idx = int(chunk_idx_str)
                except ValueError:
                    return self._send_err(f"Invalid integer value for 'X-Chunk-Index': '{chunk_idx_str}'.", status=400, code=400)

                length_hdr = self.headers.get("Content-Length")
                if length_hdr is None:
                    return self._send_err("Length Required: Content-Length header is mandatory.", status=411, code=411)
                try:
                    c_len = int(length_hdr)
                except ValueError:
                    return self._send_err("Invalid Content-Length header.", status=400, code=400)
                if c_len > (8 * 1024 * 1024 + 65536):
                    return self._send_err(f"Payload Too Large: chunk size {c_len} bytes exceeds maximum 8 MB limit.", status=413, code=413)
                if c_len <= 0:
                    return self._send_err("Chunk content cannot be empty.", status=400, code=400)

                handler = get_vision_handler()
                code, resp = handler.handle_upload_chunk(
                    upload_id=upload_id,
                    chunk_index=chunk_idx,
                    stream=self.rfile,
                    chunk_len=c_len,
                    requesting_user=user,
                    chunk_sha256=chunk_sha
                )
                return self._send_json(code, resp)

            elif path in ("/api/vision/upload/complete", "/api/vision/upload/finalize"):
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required to finalize video upload.", status=401, code=401)

                body = self._read_body()
                handler = get_vision_handler()
                code, resp = handler.handle_upload_complete(body, requesting_user=user)
                return self._send_json(code, resp)

            # Direct Video Upload (streams directly to disk without reading entire file into RAM)
            elif path == "/api/vision/upload":
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required to upload video.", status=401, code=401)

                # Rate limiting check (e.g. 10 uploads/min per user)
                allowed, retry_after = self.security.check_rate_limit("upload", user["username"])
                if not allowed:
                    self.send_response(429)
                    self.send_header("Retry-After", str(retry_after))
                    return self._send_err(f"Rate limit exceeded for video uploads. Please wait {retry_after}s.", status=429, code=429)

                # Content-Length check
                length_hdr = self.headers.get("Content-Length")
                if length_hdr is None:
                    return self._send_err("Length Required: Content-Length header is mandatory.", status=411, code=411)
                try:
                    c_len = int(length_hdr)
                except ValueError:
                    return self._send_err("Invalid Content-Length header.", status=400, code=400)
                if c_len > MAX_VIDEO_UPLOAD_SIZE:
                    return self._send_err(f"Payload Too Large: {c_len} bytes exceeds limit of {MAX_VIDEO_UPLOAD_SIZE} bytes.", status=413, code=413)
                if c_len <= 0:
                    return self._send_err("Uploaded file content cannot be empty.", status=400, code=400)

                # Content-Type check
                content_type = self.headers.get("Content-Type", "")
                base_type = content_type.split(";")[0].strip().lower()
                allowed_types = {
                    "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo",
                    "application/octet-stream", "application/json"
                }
                if base_type not in allowed_types:
                    return self._send_err(
                        f"Unsupported Media Type: '{base_type}'. Allowed types: video/mp4, video/webm, video/quicktime, application/octet-stream, application/json.",
                        status=415,
                        code=415
                    )

                filename = "uploaded_traffic_sample.mp4"
                x_filename = self.headers.get("X-Filename")
                if x_filename:
                    try:
                        filename = urllib.parse.unquote(x_filename)
                    except Exception:
                        filename = x_filename

                handler = get_vision_handler()

                if "application/json" in base_type:
                    try:
                        raw_bytes = self._read_body_raw(MAX_VIDEO_UPLOAD_SIZE)
                        parsed = json.loads(raw_bytes.decode("utf-8"))
                        if not isinstance(parsed, dict):
                            return self._send_err("Malformed JSON upload payload.", status=400, code=400)
                        if "file_data" in parsed:
                            import base64
                            raw_bytes = base64.b64decode(parsed["file_data"])
                        filename = parsed.get("filename", filename)
                        clean_filename = sanitize_filename(filename, default="sample_traffic.mp4")
                        code, resp = handler.handle_upload(raw_bytes, filename=clean_filename, owner=user["username"])
                        return self._send_json(code, resp)
                    except Exception as je:
                        return self._send_err(f"Invalid JSON video upload payload: {je}", status=400, code=400)

                clean_filename = sanitize_filename(filename, default="sample_traffic.mp4")
                code, resp = handler.handle_upload_stream(self.rfile, c_len, filename=clean_filename, owner=user["username"])
                return self._send_json(code, resp)

            elif path == "/api/vision/process":
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required to start video processing.", status=401, code=401)

                allowed, retry_after = self.security.check_rate_limit("process", user["username"])
                if not allowed:
                    self.send_response(429)
                    self.send_header("Retry-After", str(retry_after))
                    return self._send_err(f"Rate limit exceeded for video processing. Please wait {retry_after}s.", status=429, code=429)

                body = self._read_body()
                handler = get_vision_handler()
                code, resp = handler.handle_process(body, requesting_user=user)
                return self._send_json(code, resp)

            elif path == "/api/vision/live/frame":
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required for live frame processing.", status=401, code=401)
                body = self._read_body()
                handler = get_vision_handler()
                code, resp = handler.handle_process_live_frame(body, requesting_user=user)
                return self._send_json(code, resp)

            elif path == "/api/vision/live/actuate":
                user = self._get_auth_user()
                if not user:
                    return self._send_err("Unauthorized: Authentication required for live grid actuation.", status=401, code=401)
                role = user.get("role", "")
                if role != UserRole.TRAFFIC_MANAGEMENT.value:
                    return self._send_err(f"Forbidden: '{UserRole.TRAFFIC_MANAGEMENT.value}' role required for live grid actuation.", status=403, code=403)
                body = self._read_body()
                handler = get_vision_handler()
                code, resp = handler.handle_actuate_live_grid(body, requesting_user=user)
                return self._send_json(code, resp)

            # Standard JSON Body Reading
            body = self._read_body()
            eid = body.get("event_id") or body.get("id") or ""

            # 2. Authentication Routes
            if path == "/api/auth/register":
                # Public registration CANNOT elevate to Traffic Management
                user = self._get_auth_user()
                is_admin = bool(user and user.get("role") == UserRole.TRAFFIC_MANAGEMENT.value)
                ok, msg = self.security.register(
                    body.get("username", ""),
                    body.get("password", ""),
                    body.get("role", "Road User"),
                    is_admin_invoker=is_admin
                )
                return self._send_result(ok, msg)

            elif path == "/api/auth/login":
                ok, msg, session = self.security.login(body.get("username", ""), body.get("password", ""))
                return self._send_result(ok, msg, {"session": session} if ok else None, fail_status=401)

            elif path == "/api/auth/delete":
                # Admin-protected user deletion
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                ok = self.security.delete_user(body.get("username", ""))
                return self._send_result(ok, "User deleted" if ok else "User not found", fail_status=404)

            # 3. Third-Party API Configuration & Testing Endpoints
            elif path == "/api/config/tomtom":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                api_mgr = get_api_manager()
                ok, msg, data = api_mgr.update_tomtom_config(body.get("api_key", ""))
                return self._send_result(ok, msg, data)

            elif path == "/api/config/weather":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                api_mgr = get_api_manager()
                ok, msg, data = api_mgr.update_weather_config(
                    api_key=body.get("api_key"),
                    base_url=body.get("base_url")
                )
                return self._send_result(ok, msg, data)

            elif path == "/api/config/google_maps":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                api_mgr = get_api_manager()
                ok, msg, data = api_mgr.update_google_maps_config(body.get("api_key", ""))
                return self._send_result(ok, msg, data)

            elif path == "/api/config/test/tomtom":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                api_mgr = get_api_manager()
                ok, msg, data = api_mgr.test_tomtom()
                return self._send_result(ok, msg, data)

            elif path == "/api/config/test/google_maps":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                api_mgr = get_api_manager()
                ok, msg, data = api_mgr.test_google_maps()
                return self._send_result(ok, msg, data)

            elif path == "/api/config/test/weather":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                api_mgr = get_api_manager()
                ok, msg, data = api_mgr.test_weather()
                return self._send_result(ok, msg, data)

            # 4. API & System Synthesizer Endpoints (Admin Protected)
            elif path == "/api/synthesizer/handshake":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                api_mgr = get_api_manager()
                handshake_data = api_mgr.execute_multi_subsystem_handshake()
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "data": handshake_data
                })

            elif path == "/api/synthesizer/storage/backup":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                note = body.get("note", "Manual admin snapshot")
                mask_credentials = bool(body.get("mask_credentials", False))
                storage_syn = get_storage_synthesizer()
                ok, msg, data = storage_syn.create_snapshot_backup(note=note, mask_credentials=mask_credentials)
                return self._send_result(ok, msg, data)

            elif path == "/api/synthesizer/storage/restore":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                snap_id = body.get("snapshot_id", "")
                if not snap_id:
                    return self._send_err("Missing required 'snapshot_id' parameter.", status=400)
                storage_syn = get_storage_synthesizer()
                ok, msg, data = storage_syn.restore_snapshot(snap_id)
                return self._send_result(ok, msg, data)

            elif path == "/api/synthesizer/storage/prune":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                keep_count = int(body.get("keep_count", 5))
                storage_syn = get_storage_synthesizer()
                count, deleted = storage_syn.prune_old_snapshots(keep_count=keep_count)
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "pruned_count": count,
                    "deleted_snapshots": deleted,
                    "timestamp": now_iso()
                })

            elif path == "/api/synthesizer/storage/snapshot":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                snap_id = body.get("snapshot_id", "")
                if not snap_id:
                    return self._send_err("Missing required 'snapshot_id' parameter.", status=400)
                storage_syn = get_storage_synthesizer()
                ok, msg, data = storage_syn.get_snapshot_details(snap_id, mask_secrets=True)
                return self._send_result(ok, msg, data)

            elif path == "/api/synthesizer/stream/generate":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                scenario_type = body.get("scenario_type", "monsoon_flood")
                intensity = float(body.get("intensity", 0.75))
                target_zones = body.get("zones", None)
                random_seed = body.get("random_seed")
                if random_seed is not None:
                    try:
                        random_seed = int(random_seed)
                    except Exception:
                        random_seed = None
                stream_syn = get_stream_synthesizer()
                stream_data = stream_syn.generate_synthetic_stream(
                    scenario_type=scenario_type,
                    intensity=intensity,
                    target_zones=target_zones,
                    topology=self.predictor.topology if self.predictor else None,
                    random_seed=random_seed
                )
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "data": stream_data
                })

            elif path == "/api/synthesizer/predict/sandbox":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                features = body.get("features", {})
                r_id = features.get("road_id", "RD_BLR_01")
                topo_info = (self.predictor.topology.get(r_id, {}) if self.predictor and self.predictor.topology else {})

                feat_dict = {
                    "city_zone": features.get("city_zone", topo_info.get("city_zone", "Indiranagar")),
                    "road_id": r_id,
                    "intersection_id": features.get("intersection_id", topo_info.get("intersection_id", "JNC_01")),
                    "vehicle_count": float(features.get("vehicle_count", topo_info.get("avg_volume", 1450))),
                    "average_speed": float(features.get("average_speed", topo_info.get("avg_speed", 28.0))),
                    "capacity_utilization": float(features.get("capacity_utilization", 45.0)),
                    "congestion_level": features.get("congestion_level", topo_info.get("common_congestion", "Moderate")),
                    "hour": int(features.get("hour", 17)),
                    "day_of_week": int(features.get("day_of_week", 2)),
                    "is_weekend": int(features.get("is_weekend", 0))
                }

                t_infer_start = time.perf_counter()
                pred_c, prob_dict = self.predictor.predict_segment(feat_dict)
                infer_ms = round((time.perf_counter() - t_infer_start) * 1000, 3)

                # Calculate Shannon entropy: H = -sum(p * log2(p))
                import math
                entropy = 0.0
                probs_sorted = sorted(prob_dict.values(), reverse=True)
                for p_val in probs_sorted:
                    if p_val > 0.0001:
                        entropy -= p_val * math.log2(p_val)
                entropy = round(entropy, 3)

                # Confidence margin
                margin = round(probs_sorted[0] - (probs_sorted[1] if len(probs_sorted) > 1 else 0.0), 3)

                # Feature attributions
                cap_util = feat_dict["capacity_utilization"]
                spd = feat_dict["average_speed"]
                attributions = [
                    {"feature": "capacity_utilization", "value": f"{cap_util}%", "impact": "High" if cap_util > 70 else "Normal"},
                    {"feature": "average_speed", "value": f"{spd} km/h", "impact": "High" if spd < 18 else "Normal"},
                    {"feature": "vehicle_count", "value": f"{int(feat_dict['vehicle_count'])} vph", "impact": "Moderate"}
                ]

                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "prediction": {
                        "predicted_congestion": pred_c,
                        "probabilities": prob_dict,
                        "confidence_margin": margin,
                        "shannon_entropy": entropy,
                        "inference_latency_ms": infer_ms,
                        "input_features": feat_dict,
                        "attributions": attributions
                    },
                    "timestamp": now_iso()
                })

            # 4. Municipal Event Management Endpoints (Admin Protected)
            elif path == "/api/events/publish":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                ok, msg, evt = self.event_mgr.publish_event(eid, updates=body)
                return self._send_result(ok, msg, {"event": evt} if ok else None)

            elif path in ("/api/events/unpublish", "/api/events/retract"):
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                ok, msg = self.event_mgr.unpublish_event(eid)
                return self._send_result(ok, msg, fail_status=404)

            elif path == "/api/events/add":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                ok, msg, evt = self.event_mgr.add_event(body)
                return self._send_result(ok, msg, {"event": evt} if ok else None)

            elif path == "/api/events/delete":
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                ok, msg = self.event_mgr.delete_event(eid)
                return self._send_result(ok, msg, fail_status=404)

            elif path in ("/api/events/sync", "/api/events/live/sync"):
                auth_ok, auth_err, auth_code = self._check_admin_auth()
                if not auth_ok:
                    return self._send_err(auth_err, status=auth_code)
                zone = body.get("zone")
                events = self.event_mgr.sync_bengaluru_live_incidents(zone=zone)
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "message": f"Synchronized live Bengaluru incidents for zone: {zone or 'all'}",
                    "count": len(events),
                    "events": events,
                    "timestamp": now_iso()
                })

            # 5. Routing & Junction Intelligence
            elif path in ("/api/route/evaluate", "/api/evaluate_route"):
                now_dt = datetime.datetime.now()
                default_date = now_dt.strftime("%Y-%m-%d")
                default_time = now_dt.strftime("%H:%M")

                orig = str(body.get("origin_road") or "RD_BLR_01").strip()
                dest = str(body.get("destination_road") or "RD_BLR_04").strip()
                if not is_valid_identifier(orig) or not is_valid_identifier(dest):
                    return self._send_err(f"Invalid corridor identifier format: orig='{orig}', dest='{dest}'.", status=400, code=400)

                date_val = str(body.get("departure_date") or body.get("date") or default_date).strip()
                try:
                    datetime.date.fromisoformat(date_val)
                except Exception:
                    return self._send_err(f"Invalid 'date' format: '{date_val}'. Expected YYYY-MM-DD.", status=400, code=400)

                time_val = str(body.get("departure_time") or body.get("time") or default_time).strip()
                try:
                    parse_time_str(time_val)
                except Exception:
                    return self._send_err(f"Invalid 'time' format: '{time_val}'. Expected HH:MM.", status=400, code=400)

                evaluation = self.navigator.evaluate_route(orig, dest, date_val, time_val)
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "evaluation": evaluation.to_dict(),
                    "data": evaluation.to_dict(),
                    "timestamp": now_iso()
                })

            elif path == "/api/map/route_lanes":
                now_dt = datetime.datetime.now()
                default_date = now_dt.strftime("%Y-%m-%d")
                default_time = now_dt.strftime("%H:%M")

                orig = str(body.get("origin_road") or "RD_BLR_01").strip()
                dest = str(body.get("destination_road") or "RD_BLR_04").strip()
                if not is_valid_identifier(orig) or not is_valid_identifier(dest):
                    return self._send_err(f"Invalid corridor identifier format: orig='{orig}', dest='{dest}'.", status=400, code=400)

                date_val = str(body.get("departure_date") or body.get("date") or default_date).strip()
                try:
                    datetime.date.fromisoformat(date_val)
                except Exception:
                    return self._send_err(f"Invalid 'date' format: '{date_val}'. Expected YYYY-MM-DD.", status=400, code=400)

                time_val = str(body.get("departure_time") or body.get("time") or default_time).strip()
                try:
                    parse_time_str(time_val)
                except Exception:
                    return self._send_err(f"Invalid 'time' format: '{time_val}'. Expected HH:MM.", status=400, code=400)

                evaluation = self.navigator.evaluate_route(orig, dest, date_val, time_val)
                eval_dict = evaluation.to_dict()
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "evaluation": eval_dict,
                    "primary_polylines": eval_dict.get("primary_polylines", []),
                    "recommended_polylines": eval_dict.get("recommended_polylines", []),
                    "primary_lane_guidance": eval_dict.get("primary_lane_guidance", []),
                    "recommended_lane_guidance": eval_dict.get("recommended_lane_guidance", []),
                    "timestamp": now_iso()
                })

            elif path == "/api/junction/telemetry":
                now_dt = datetime.datetime.now()
                raw_time = str(body.get("time") or now_dt.strftime("%H:%M")).strip()
                try:
                    hour, minute = parse_time_str(raw_time)
                except Exception:
                    return self._send_err(f"Invalid 'time' value: '{raw_time}'. Expected HH:MM format.", status=400, code=400)

                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    return self._send_err(f"Time out of range: hour {hour} (0-23), minute {minute} (0-59).", status=400, code=400)

                road_id = str(body.get("road_id") or "RD_BLR_01").strip()
                if not is_valid_identifier(road_id):
                    return self._send_err(f"Invalid 'road_id' format: '{road_id}'.", status=400, code=400)

                alt_road = body.get("alternate_road")
                if alt_road:
                    alt_road = str(alt_road).strip()
                    if not is_valid_identifier(alt_road):
                        return self._send_err(f"Invalid 'alternate_road' format: '{alt_road}'.", status=400, code=400)

                date_str = str(body.get("date") or now_dt.strftime("%Y-%m-%d")).strip()
                try:
                    datetime.date.fromisoformat(date_str)
                except Exception:
                    return self._send_err(f"Invalid 'date' format: '{date_str}'. Expected YYYY-MM-DD.", status=400, code=400)

                telemetry = self.junction_service.get_junction_telemetry(
                    road_id=road_id,
                    hour=hour, minute=minute,
                    is_rerouted=bool(body.get("is_rerouted", False)),
                    alternate_road_id=alt_road,
                    date_str=date_str
                )

                # Explicitly identify simulated telemetry provenance
                telemetry["is_simulated"] = True
                telemetry["data_provenance"] = "Junction Signal Control Simulation Engine"

                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "junction": telemetry,
                    "data": telemetry,
                    "timestamp": now_iso()
                })

            elif path in ("/api/simulation/run", "/api/simulate", "/api/simulation"):
                result = self.simulator.simulate_zone_policy(
                    body.get("zone", None),
                    float(body.get("alpha", 0.20)),
                    float(body.get("beta", 0.10)),
                    int(body.get("hour", 17)),
                    int(body.get("day_of_week", 3))
                )
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "simulation": result,
                    "data": result,
                    "timestamp": now_iso()
                })

            elif path == "/api/predict/explain":
                explanation = self.predictor.predict_segment(body.get("features", {}), explain=True)
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "explanation": explanation,
                    "data": explanation,
                    "timestamp": now_iso()
                })

            # 6. Live Telemetry & Evaluation
            elif path == "/api/live/refresh":
                # Protected/Rate-limited expensive external refresh
                user = self._get_auth_user()
                client_id = user["username"] if user else (self.client_address[0] if hasattr(self, "client_address") else "anonymous")
                is_admin = bool(user and user.get("role") == UserRole.TRAFFIC_MANAGEMENT.value)

                if not is_admin:
                    allowed, retry_after = self.security.check_rate_limit("live_refresh", client_id)
                    if not allowed:
                        self.send_response(429)
                        self.send_header("Retry-After", str(retry_after))
                        return self._send_err(f"Rate limit exceeded for live data refresh. Please wait {retry_after}s.", status=429, code=429)

                corridors = self.bridge.get_corridor_telemetry(force_refresh=True)
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "count": len(corridors),
                    "corridors": corridors,
                    "status_info": self.bridge.get_live_status(),
                    "timestamp": now_iso()
                })

            elif path in ("/api/live/corridors", "/api/live/telemetry"):
                zone = body.get("zone")
                force = bool(body.get("force_refresh", False))
                if force:
                    user = self._get_auth_user()
                    client_id = user["username"] if user else (self.client_address[0] if hasattr(self, "client_address") else "anonymous")
                    allowed, retry_after = self.security.check_rate_limit("live_refresh", client_id)
                    if not allowed:
                        self.send_response(429)
                        self.send_header("Retry-After", str(retry_after))
                        return self._send_err(f"Rate limit exceeded for live refresh. Please wait {retry_after}s.", status=429, code=429)

                corridors = self.bridge.get_corridor_telemetry(force_refresh=force)
                if zone and str(zone).lower() != "all":
                    corridors = [c for c in corridors if c["city_zone"].lower() == str(zone).lower()]
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "count": len(corridors),
                    "corridors": corridors,
                    "status_info": self.bridge.get_live_status(),
                    "timestamp": now_iso()
                })

            elif path in ("/api/live/route", "/api/live/evaluate_route"):
                res = self.bridge.evaluate_live_route(
                    body.get("origin_road") or "RD_BLR_01",
                    body.get("destination_road") or "RD_BLR_02",
                    event_mgr=self.event_mgr,
                    date=body.get("date"),
                    time_str=body.get("time"),
                    published_only=not (body.get("all") or False)
                )
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "evaluation": res,
                    "data": res,
                    "timestamp": now_iso()
                })

            elif path == "/api/live/predict":
                features = body.get("features")
                if not isinstance(features, dict):
                    return self._send_err("Missing or invalid 'features' object in request body.", status=400, code=400)

                # Schema validation for numerical ranges
                if "hour" in features:
                    try:
                        h = int(features["hour"])
                        if not (0 <= h <= 23):
                            return self._send_err(f"Feature 'hour' must be between 0 and 23 (got {h}).", status=400, code=400)
                    except (ValueError, TypeError):
                        return self._send_err("Feature 'hour' must be a valid integer.", status=400, code=400)

                if "day_of_week" in features:
                    try:
                        dow = int(features["day_of_week"])
                        if not (0 <= dow <= 6):
                            return self._send_err(f"Feature 'day_of_week' must be between 0 and 6 (got {dow}).", status=400, code=400)
                    except (ValueError, TypeError):
                        return self._send_err("Feature 'day_of_week' must be a valid integer.", status=400, code=400)

                if "vehicle_count" in features:
                    try:
                        vc = float(features["vehicle_count"])
                        if vc < 0:
                            return self._send_err(f"Feature 'vehicle_count' cannot be negative (got {vc}).", status=400, code=400)
                    except (ValueError, TypeError):
                        return self._send_err("Feature 'vehicle_count' must be a valid number.", status=400, code=400)

                if "average_speed" in features:
                    try:
                        sp = float(features["average_speed"])
                        if sp <= 0:
                            return self._send_err(f"Feature 'average_speed' must be positive (got {sp}).", status=400, code=400)
                    except (ValueError, TypeError):
                        return self._send_err("Feature 'average_speed' must be a valid number.", status=400, code=400)

                pred_class, prob_dist = self.bridge.predictor.predict_segment(features)

                provenance = {
                    "model_name": "XGBoost Pure-Python Tree Ensemble",
                    "dataset_version": self.predictor.metrics.get("dataset_version", "Bangalore-Traffic-v2.1") if self.predictor else "Bangalore-Traffic-v2.1",
                    "model_version": self.predictor.metrics.get("model_version", "2.1.0") if self.predictor else "2.1.0",
                    "temporal_validation": "Chronological Out-of-Time Date Grouping",
                    "inference_engine": "Deterministic Tree Traversal"
                }

                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "predicted_class": pred_class,
                    "probabilities": prob_dist,
                    "provenance": provenance,
                    "model_provenance": provenance,
                    "timestamp": now_iso()
                })

            self._send_err(f"Endpoint '{path}' not found", status=404, code=404)
        except ValueError as ve:
            msg = str(ve)
            logger.warning("Client request validation error on %s: %s", getattr(self, "path", "/"), msg)
            if "Payload Too Large" in msg:
                self._send_err(msg, status=413, code=413)
            elif "Length Required" in msg:
                self._send_err(msg, status=411, code=411)
            elif "Unsupported Media Type" in msg:
                self._send_err(msg, status=415, code=415)
            elif "Forbidden" in msg:
                self._send_err(msg, status=403, code=403)
            elif "Unauthorized" in msg:
                self._send_err(msg, status=401, code=401)
            else:
                self._send_err(msg, status=400, code=400)
        except Exception as e:
            logger.error("Unhandled POST error on %s: %s", getattr(self, "path", "/"), e, exc_info=True)
            self._send_err("An internal server error occurred.", status=500, code=500)


def run_server(port: int = 8080, predictor: Optional[TrafficPredictor] = None, event_mgr: Optional[EventManager] = None):
    TrafficAppServer.ensure_initialized(predictor=predictor, event_mgr=event_mgr)

    ThreadingHTTPServer.allow_reuse_address = True
    server = None
    active_port = port
    for candidate_port in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("0.0.0.0", candidate_port), TrafficAppServer)
            active_port = candidate_port
            break
        except OSError:
            continue

    if server is None:
        raise OSError(f"Could not bind to any port in range {port}-{port+20}")

    print(f"=================================================================")
    print(f" Traffic AI High-Performance Threading Server Live on http://0.0.0.0:{active_port}")
    print(f" Commuter Navigator & Traffic Management Control Room Active")
    print(f"=================================================================")

    def _heartbeat_worker():
        while True:
            time.sleep(30)
            try:
                sys.stdout.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Traffic AI Server Heartbeat: Port {active_port} active & responsive.\n")
                sys.stdout.flush()
            except Exception:
                break

    hb_thread = threading.Thread(target=_heartbeat_worker, daemon=True)
    hb_thread.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)

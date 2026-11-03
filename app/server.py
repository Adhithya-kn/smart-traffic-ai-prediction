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
    CORS_ALLOWED_ORIGINS
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
from app.routes.vision_routes import get_vision_handler
from traffic_system.core.time_utils import parse_time_parts as parse_time_str
from traffic_system.core.road_registry import get_road_name

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
        "/index.html", "/static/index.html", "/app/static/index.html"
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

    def _send_json(self, status: int, data: Dict[str, Any]):
        """Transmits JSON response with standard CORS headers."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOWED_ORIGINS)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
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
        """Extracts and validates active user session from Bearer token."""
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            return self.security.get_user_by_token(token)
        return None

    def _check_admin_auth(self) -> Tuple[bool, Optional[str], int]:
        """
        Validates administrator role for protected endpoints.
        Returns (is_authorized, error_message, http_status).
        """
        user = self._get_auth_user()
        if user:
            role = user.get("role", "")
            if role in (UserRole.TRAFFIC_MANAGEMENT.value, "Traffic Authority"):
                return True, None, 200
            return False, "Forbidden: Administrator privileges required.", 403

        if ENFORCE_ADMIN_AUTH:
            return False, "Unauthorized: Valid administrator Bearer token required.", 401

        # Non-enforced dev/test mode without token
        return True, None, 200

    def do_OPTIONS(self):
        """Handles CORS pre-flight inquiries."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOWED_ORIGINS)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.end_headers()

    def _read_body_raw(self, max_bytes: int = MAX_REQUEST_BODY_SIZE) -> bytes:
        """Reads raw request body safely with payload size verification."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > max_bytes:
                raise ValueError(f"Payload Too Large: {length} bytes exceeds limit of {max_bytes} bytes.")
            if length > 0:
                return self.rfile.read(length)
        except Exception as e:
            if "Payload Too Large" in str(e):
                raise
        return b""

    def _read_body(self) -> Dict[str, Any]:
        """Parses JSON body safely."""
        try:
            raw = self._read_body_raw(MAX_REQUEST_BODY_SIZE)
            if raw:
                return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise
        except Exception:
            pass
        return {}

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
                rel_path = path[len("/architecture/"):].strip("/")
                arch_file = (BASE_DIR / "architecture" / rel_path).resolve()
                mime = "text/html; charset=utf-8" if arch_file.suffix == ".html" else "text/plain; charset=utf-8"
                if self._serve_file(arch_file, content_type=mime):
                    return

            # Health & Readiness Endpoints
            if path in ("/api/health", "/api/health/readiness"):
                is_readiness = (path == "/api/health/readiness") or q_bool("readiness") or (q("type") == "readiness")
                if is_readiness:
                    checks = {
                        "predictor_loaded": self.predictor.is_trained() and bool(self.predictor.topology),
                        "event_engine_ready": len(self.event_mgr.events) > 0,
                        "storage_writeable": self.event_mgr.db_path.parent.exists(),
                        "security_db_ready": len(self.security.users) > 0
                    }
                    all_ready = all(checks.values())
                    status_code = 200 if all_ready else 503
                    return self._send_json(status_code, {
                        "success": all_ready,
                        "status": "ready" if all_ready else "not_ready",
                        "service": "Smart Traffic AI",
                        "readiness": all_ready,
                        "checks": checks,
                        "timestamp": now_iso()
                    })

                # Simple liveness/availability probe
                return self._send_json(200, {
                    "success": True,
                    "status": "healthy",
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
            elif path == "/api/vision/status":
                handler = get_vision_handler()
                code, resp = handler.handle_get_status()
                return self._send_json(code, resp)

            elif path.startswith("/api/vision/jobs/"):
                job_id = path[len("/api/vision/jobs/"):].strip("/")
                handler = get_vision_handler()
                code, resp = handler.handle_get_job(job_id)
                return self._send_json(code, resp)

            elif path.startswith("/api/vision/results/"):
                job_id = path[len("/api/vision/results/"):].strip("/")
                handler = get_vision_handler()
                code, resp = handler.handle_get_results(job_id)
                return self._send_json(code, resp)

            elif path.startswith("/api/vision/video/"):
                job_id = path[len("/api/vision/video/"):].strip("/")
                handler = get_vision_handler()
                code, vbytes, mime = handler.handle_get_video(job_id)
                if code == 200 and vbytes is not None:
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(vbytes)))
                    self.end_headers()
                    self.wfile.write(vbytes)
                    return
                return self._send_err(mime or "Video not found", status=code)

            super().do_GET()
        except ValueError as ve:
            self._send_err(str(ve), status=413)
        except Exception as e:
            logger.error("Unhandled GET error on %s: %s", getattr(self, "path", "/"), e, exc_info=True)
            self._send_err("An internal server error occurred.", status=500, code=500)

    def do_POST(self):
        try:
            url = urllib.parse.urlparse(self.path)
            path = url.path

            # 1. Computer Vision Upload (supports raw binary MP4 or form payload)
            if path == "/api/vision/upload":
                try:
                    raw_bytes = self._read_body_raw(MAX_VIDEO_UPLOAD_SIZE)
                except ValueError as ve:
                    return self._send_err(str(ve), status=413)

                content_type = self.headers.get("Content-Type", "")
                filename = "uploaded_traffic_sample.mp4"

                # Check if JSON payload wrapping base64
                if "application/json" in content_type:
                    try:
                        parsed = json.loads(raw_bytes.decode("utf-8"))
                        if "file_data" in parsed:
                            import base64
                            raw_bytes = base64.b64decode(parsed["file_data"])
                        filename = parsed.get("filename", filename)
                    except Exception:
                        pass

                handler = get_vision_handler()
                code, resp = handler.handle_upload(raw_bytes, filename=filename)
                return self._send_json(code, resp)

            elif path == "/api/vision/process":
                body = self._read_body()
                handler = get_vision_handler()
                code, resp = handler.handle_process(body)
                return self._send_json(code, resp)

            # Standard JSON Body Reading
            body = self._read_body()
            eid = body.get("event_id") or body.get("id") or ""

            # 2. Authentication Routes
            if path == "/api/auth/register":
                # Public registration CANNOT elevate to Traffic Management
                user = self._get_auth_user()
                is_admin = bool(user and user.get("role") in (UserRole.TRAFFIC_MANAGEMENT.value, "Traffic Authority"))
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

            elif path == "/api/config/test/tomtom":
                api_mgr = get_api_manager()
                ok, msg, data = api_mgr.test_tomtom()
                return self._send_result(ok, msg, data)

            elif path == "/api/config/test/weather":
                api_mgr = get_api_manager()
                ok, msg, data = api_mgr.test_weather()
                return self._send_result(ok, msg, data)

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
                orig, dest = body.get("origin_road") or "RD_BLR_01", body.get("destination_road") or "RD_BLR_04"
                evaluation = self.navigator.evaluate_route(orig, dest, body.get("date") or "2026-03-18", body.get("time") or "09:00")
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "evaluation": evaluation.to_dict(),
                    "data": evaluation.to_dict(),
                    "timestamp": now_iso()
                })

            elif path == "/api/junction/telemetry":
                hour, minute = parse_time_str(body.get("time", "17:00"))
                telemetry = self.junction_service.get_junction_telemetry(
                    road_id=body.get("road_id", "RD_BLR_01"),
                    hour=hour, minute=minute,
                    is_rerouted=bool(body.get("is_rerouted", False)),
                    alternate_road_id=body.get("alternate_road", None),
                    date_str=body.get("date", "2026-03-18")
                )
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
            elif path in ("/api/live/refresh", "/api/live/corridors"):
                corridors = self.bridge.get_corridor_telemetry(force_refresh=True)
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
                pred_class, prob_dist = self.bridge.predictor.predict_segment(body.get("features", {}))
                return self._send_json(200, {
                    "success": True,
                    "status": "success",
                    "predicted_class": pred_class,
                    "probabilities": prob_dist,
                    "timestamp": now_iso()
                })

            self._send_err(f"Endpoint '{path}' not found", status=404, code=404)
        except ValueError as ve:
            self._send_err(str(ve), status=413, code=413)
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

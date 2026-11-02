"""
app/server.py - High-Performance Threading REST API & Application Server
Serves the Dual-Persona Obsidian Luxury Interface and REST endpoints.
"""

import sys
import json
import time
import datetime
import threading
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from traffic_system.config import BASE_DIR
from traffic_system.core.security import SecurityManager
from traffic_system.events.event_manager import EventManager
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.routing.navigator import RouteNavigator
from traffic_system.simulation.counterfactual import PolicySimulator
from traffic_system.dispatch.recommender import generate_action_directive
from traffic_system.junction.junction_service import JunctionService
from traffic_system.live.bridge import LiveTrafficDataBridge, get_live_bridge
from traffic_system.core.time_utils import parse_time_parts as parse_time_str

STATIC_DIR = BASE_DIR / "app" / "static"

class TrafficAppServer(SimpleHTTPRequestHandler):
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
        if cls.predictor is None:
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

    def _send_result(self, ok: bool, msg: str, data: Optional[Dict[str, Any]] = None, fail_status: int = 400):
        if ok:
            self._send_ok(data=data, message=msg)
        else:
            self._send_err(message=msg, status=fail_status)

    def _send_json(self, status: int, data: Dict[str, Any]):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _send_ok(self, data: Optional[Dict[str, Any]] = None, message: Optional[str] = None, status: int = 200, **kwargs):
        payload = {"status": "success", **(data or {}), **kwargs}
        if message is not None:
            payload["message"] = message
        self._send_json(status, payload)

    def _send_err(self, message: str, status: int = 400, code: Optional[int] = None, **kwargs):
        payload = {"status": "error", "message": message, **kwargs}
        if code is not None:
            payload["code"] = code
        self._send_json(status, payload)

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

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _read_body(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw)
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

            # Default entry & Login routes -> Serve clean Login Page directly
            if path in self.LOGIN_ROUTES:
                if self._serve_file(STATIC_DIR / "login.html"):
                    return

            # Dedicated Portal and Live Simulation routes -> Serve Viewport
            if path in self.PORTAL_ROUTES or path in self.LIVE_ROUTES:
                if self._serve_file(STATIC_DIR / "index.html"):
                    return

            if path.startswith("/architecture/"):
                rel_path = path[len("/architecture/"):].strip("/")
                arch_file = (BASE_DIR / "architecture" / rel_path).resolve()
                mime = "text/html; charset=utf-8" if arch_file.suffix == ".html" else "text/plain; charset=utf-8"
                if self._serve_file(arch_file, content_type=mime):
                    return

            if path == "/api/health":
                return self._send_json(200, {"status": "healthy", "service": "Smart Traffic AI", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()})

            if path == "/api/roads":
                roads = self.navigator.get_available_roads(q("zone"))
                return self._send_json(200, {"status": "success", "count": len(roads), "roads": roads})

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
                
                # Ensure all events have human-readable affected_road_names populated
                for evt in events:
                    if "affected_roads" in evt and not evt.get("affected_road_names"):
                        evt["affected_road_names"] = [get_road_name(r) for r in evt["affected_roads"]]

                return self._send_json(200, {
                    "status": "success",
                    "count": len(events),
                    "is_historical": is_history,
                    "events": events,
                    "latest_alert": self.event_mgr.get_latest_alert()
                })

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
                return self._send_json(200, {"status": "success", "metrics": metrics})

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
                return self._send_json(200, {"status": "success", "count": len(directives), "directives": directives})

            elif path == "/api/zones/summary":
                zone_crit_scores = {}
                for r_id, info in self.predictor.topology.items():
                    pdist = info.get("pred_dist", {})
                    zone_crit_scores.setdefault(info["city_zone"], []).append((pdist.get("High", 0.0) + pdist.get("Severe", 0.0)) * 100.0)
                result = sorted([
                    {"zone": z, "total_roads": len(s), "pct_critical": round(sum(s) / len(s), 1) if s else 0.0}
                    for z, s in zone_crit_scores.items()
                ], key=lambda x: -x["pct_critical"])
                return self._send_json(200, {"status": "success", "zones": result})

            elif path == "/api/live/status":
                return self._send_json(200, self.bridge.get_live_status())

            elif path in ("/api/live/telemetry", "/api/live/corridors"):
                zone = q("zone")
                corridors = self.bridge.get_corridor_telemetry()
                if zone and zone.lower() != "all":
                    corridors = [c for c in corridors if c["city_zone"].lower() == zone.lower()]
                return self._send_json(200, {
                    "status": "success",
                    "count": len(corridors),
                    "corridors": corridors,
                    "status_info": self.bridge.get_live_status()
                })

            # Static asset fallback
            super().do_GET()
        except Exception as e:
            self._send_json(500, {"status": "error", "message": f"Server error: {str(e)}", "code": 500})

    def do_POST(self):
        try:
            url = urllib.parse.urlparse(self.path)
            path = url.path
            body = self._read_body()

            eid = body.get("event_id") or body.get("id") or ""

            if path == "/api/auth/register":
                ok, msg = self.security.register(body.get("username", ""), body.get("password", ""), body.get("role", "Road User"))
                return self._send_result(ok, msg)

            elif path == "/api/auth/login":
                ok, msg, session = self.security.login(body.get("username", ""), body.get("password", ""))
                return self._send_result(ok, msg, {"session": session} if ok else None, fail_status=401)

            elif path == "/api/auth/delete":
                ok = self.security.delete_user(body.get("username", ""))
                return self._send_result(ok, "User deleted" if ok else "User not found", fail_status=404)

            elif path == "/api/events/publish":
                ok, msg, evt = self.event_mgr.publish_event(eid, updates=body)
                return self._send_result(ok, msg, {"event": evt} if ok else None)

            elif path in ("/api/events/unpublish", "/api/events/retract"):
                ok, msg = self.event_mgr.unpublish_event(eid)
                return self._send_result(ok, msg, fail_status=404)

            elif path == "/api/events/add":
                ok, msg, evt = self.event_mgr.add_event(body)
                return self._send_result(ok, msg, {"event": evt} if ok else None)

            elif path == "/api/events/delete":
                ok, msg = self.event_mgr.delete_event(eid)
                return self._send_result(ok, msg, fail_status=404)

            elif path in ("/api/events/sync", "/api/events/live/sync"):
                zone = body.get("zone")
                events = self.event_mgr.sync_bengaluru_live_incidents(zone=zone)
                return self._send_json(200, {
                    "status": "success",
                    "message": f"Synchronized live Bengaluru incidents for zone: {zone or 'all'}",
                    "count": len(events),
                    "events": events
                })

            elif path == "/api/route/evaluate":
                orig, dest = body.get("origin_road") or "RD_BLR_01", body.get("destination_road") or "RD_BLR_04"
                evaluation = self.navigator.evaluate_route(orig, dest, body.get("date") or "2026-03-18", body.get("time") or "09:00")
                return self._send_json(200, {"status": "success", "evaluation": evaluation.to_dict()})

            elif path == "/api/junction/telemetry":
                hour, minute = parse_time_str(body.get("time", "17:00"))
                telemetry = self.junction_service.get_junction_telemetry(
                    road_id=body.get("road_id", "RD_BLR_01"),
                    hour=hour, minute=minute,
                    is_rerouted=bool(body.get("is_rerouted", False)),
                    alternate_road_id=body.get("alternate_road", None),
                    date_str=body.get("date", "2026-03-18")
                )
                return self._send_json(200, {"status": "success", "junction": telemetry})

            elif path == "/api/simulation/run":
                result = self.simulator.simulate_zone_policy(
                    body.get("zone", None),
                    float(body.get("alpha", 0.20)),
                    float(body.get("beta", 0.10)),
                    int(body.get("hour", 17)),
                    int(body.get("day_of_week", 3))
                )
                return self._send_json(200, {"status": "success", "simulation": result})

            elif path == "/api/predict/explain":
                return self._send_json(200, {"status": "success", "explanation": self.predictor.predict_segment(body.get("features", {}), explain=True)})

            elif path == "/api/live/refresh":
                corridors = self.bridge.get_corridor_telemetry(force_refresh=True)
                return self._send_json(200, {
                    "status": "success",
                    "count": len(corridors),
                    "corridors": corridors,
                    "status_info": self.bridge.get_live_status()
                })

            elif path == "/api/live/route":
                res = self.bridge.evaluate_live_route(
                    body.get("origin_road") or "RD_BLR_01",
                    body.get("destination_road") or "RD_BLR_02",
                    event_mgr=self.event_mgr
                )
                return self._send_json(200, {"status": "success", "evaluation": res})

            elif path == "/api/live/predict":
                pred_class, prob_dist = self.bridge.predictor.predict_segment(body.get("features", {}))
                return self._send_json(200, {
                    "status": "success",
                    "predicted_class": pred_class,
                    "probabilities": prob_dist
                })
                return

            self._send_json(404, {"error": f"Endpoint '{path}' not found"})
        except Exception as e:
            self._send_json(500, {"status": "error", "message": f"Server error: {str(e)}", "code": 500})

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
        except OSError as e:
            if candidate_port == port:
                print(f"  [Notice] Port {candidate_port} is already in use by another instance. Searching for next available port...")
            continue

    if server is None:
        raise OSError(f"Could not bind to any port in range {port}-{port+20}")

    print(f"=================================================================")
    print(f" Traffic AI High-Performance Threading Server Live on http://localhost:{active_port}")
    print(f" Commuter Navigator & Traffic Management Control Room Active")
    print(f"=================================================================")

    def _heartbeat_worker():
        import time, datetime
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

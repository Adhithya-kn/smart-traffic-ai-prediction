"""
app/server.py - High-Performance Threading REST API & Application Server
Serves the Dual-Persona Obsidian Luxury Interface and REST endpoints.
"""

import sys
import json
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

def parse_time_str(time_str: str):
    """Robust parser for both 24-hour ('17:00') and 12-hour ('05:00 PM') strings."""
    try:
        t = str(time_str).strip()
        if "PM" in t.upper() or "AM" in t.upper():
            parts = t.replace("PM", "").replace("AM", "").strip().split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            if "PM" in t.upper() and h < 12:
                h += 12
            elif "AM" in t.upper() and h == 12:
                h = 0
            return h, m
        parts = t.split(":")
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        return 17, 0

STATIC_DIR = BASE_DIR / "app" / "static"

class TrafficAppServer(SimpleHTTPRequestHandler):
    security: SecurityManager = None
    event_mgr: EventManager = None
    predictor: TrafficPredictor = None
    navigator: RouteNavigator = None
    simulator: PolicySimulator = None
    junction_service: JunctionService = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _send_json(self, status: int, data: Dict[str, Any]):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

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

    def do_HEAD(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path in ("/", "", "/login", "/login/", "/signin", "/signin/"):
            login_file = STATIC_DIR / "login.html"
            if login_file.exists():
                content = login_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                return
        if path in ("/portal", "/portal/", "/dashboard", "/dashboard/", "/app", "/app/"):
            portal_file = STATIC_DIR / "index.html"
            if portal_file.exists():
                content = portal_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                return
        super().do_HEAD()

    def do_GET(self):
        try:
            url = urllib.parse.urlparse(self.path)
            path = url.path
            query = urllib.parse.parse_qs(url.query)

            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return

            # Default entry & Login routes -> Serve clean Login Page directly
            if path in ("/", "", "/login", "/login/", "/signin", "/signin/"):
                login_file = STATIC_DIR / "login.html"
                if login_file.exists():
                    content = login_file.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return

            # Dedicated Portal routes -> Serve User/Authority Console Viewport
            if path in ("/portal", "/portal/", "/dashboard", "/dashboard/", "/app", "/app/"):
                portal_file = STATIC_DIR / "index.html"
                if portal_file.exists():
                    content = portal_file.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return

            if path.startswith("/architecture/"):
                rel_path = path[len("/architecture/"):].strip("/")
                arch_file = (BASE_DIR / "architecture" / rel_path).resolve()
                if arch_file.exists() and arch_file.is_file() and str(arch_file).startswith(str(BASE_DIR / "architecture")):
                    content = arch_file.read_bytes()
                    mime = "text/html; charset=utf-8" if arch_file.suffix == ".html" else "text/plain; charset=utf-8"
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return

            if path == "/api/roads":
                zone = query.get("zone", [None])[0]
                roads = self.navigator.get_available_roads(zone)
                self._send_json(200, {"status": "success", "count": len(roads), "roads": roads})
                return

            elif path in ("/api/events", "/api/events/historical"):
                zone = query.get("zone", [None])[0]
                date = query.get("date", [None])[0]
                is_history = path == "/api/events/historical" or query.get("history", ["false"])[0].lower() in ("true", "1", "yes")
                if is_history:
                    events = self.event_mgr.get_historical_events(zone=zone)
                elif zone or date:
                    events = self.event_mgr.find_active_events(zone=zone, date=date)
                else:
                    events = self.event_mgr.get_scheduled_events(zone=zone)
                self._send_json(200, {"status": "success", "count": len(events), "is_historical": is_history, "events": events})
                return

            elif path == "/api/metrics":
                metrics = self.predictor.metrics
                self._send_json(200, {"status": "success", "metrics": metrics})
                return

            elif path == "/api/dispatch/directives":
                zone = query.get("zone", [None])[0]
                if not zone:
                    zone = "Indiranagar"
                roads = self.navigator.get_available_roads(zone)
                directives = []
                import datetime
                now = datetime.datetime.now()
                hour = now.hour
                dow = now.weekday()
                is_weekend = 1 if dow >= 5 else 0
                for r in roads[:10]:
                    r_id = r["road_id"]
                    features = {
                        "city_zone": r["city_zone"],
                        "road_id": r_id,
                        "intersection_id": r["intersection_id"],
                        "vehicle_count": r.get("peak_volume", r["avg_volume"]),
                        "average_speed": r.get("peak_speed", r["avg_speed"]),
                        "capacity_utilization": round((r.get("peak_volume", r["avg_volume"]) / max(r.get("capacity", 35000), 1)) * 100, 1),
                        "congestion_level": r.get("peak_congestion", r.get("common_congestion", "Moderate")),
                        "hour": hour,
                        "day_of_week": dow,
                        "is_weekend": is_weekend
                    }
                    pred_cong, _ = self.predictor.predict_segment(features)
                    evts = self.event_mgr.find_active_events(road_id=r_id)
                    has_evt = len(evts) > 0
                    evt_name = evts[0]["name"] if has_evt else ""
                    directive = generate_action_directive(r_id, zone, pred_cong, has_evt, evt_name)
                    directives.append(directive)
                self._send_json(200, {"status": "success", "count": len(directives), "directives": directives})
                return

            elif path == "/api/zones/summary":
                zone_crit_scores = {}
                for r_id, info in self.predictor.topology.items():
                    z = info["city_zone"]
                    pdist = info.get("pred_dist", {})
                    crit_ratio = pdist.get("High", 0.0) + pdist.get("Severe", 0.0)
                    zone_crit_scores.setdefault(z, []).append(crit_ratio * 100.0)

                result = []
                for zone_name, scores in zone_crit_scores.items():
                    total = len(scores)
                    avg_critical = round(sum(scores) / total, 1) if total > 0 else 42.0
                    result.append({
                        "zone": zone_name,
                        "total_roads": total,
                        "pct_critical": avg_critical
                    })
                result.sort(key=lambda x: -x["pct_critical"])
                self._send_json(200, {"status": "success", "zones": result})
                return

            # Static asset fallback
            super().do_GET()
        except Exception as e:
            self._send_json(500, {"status": "error", "message": f"Server error: {str(e)}", "code": 500})

    def do_POST(self):
        try:
            url = urllib.parse.urlparse(self.path)
            path = url.path
            body = self._read_body()

            if path == "/api/auth/register":
                username = body.get("username", "")
                password = body.get("password", "")
                role = body.get("role", "Commuter")
                ok, msg = self.security.register(username, password, role)
                status = 200 if ok else 400
                self._send_json(status, {"status": "success" if ok else "error", "message": msg})
                return

            elif path == "/api/auth/login":
                username = body.get("username", "")
                password = body.get("password", "")
                ok, msg, session = self.security.login(username, password)
                status = 200 if ok else 401
                self._send_json(status, {"status": "success" if ok else "error", "message": msg, "session": session})
                return

            elif path == "/api/auth/delete":
                username = body.get("username", "")
                ok = self.security.delete_user(username)
                status = 200 if ok else 404
                self._send_json(status, {"status": "success" if ok else "error", "message": "User deleted" if ok else "User not found"})
                return

            elif path == "/api/events/add":
                ok, msg, evt = self.event_mgr.add_event(body)
                status = 200 if ok else 400
                self._send_json(status, {"status": "success" if ok else "error", "message": msg, "event": evt})
                return

            elif path == "/api/events/delete":
                event_id = body.get("event_id") or body.get("id") or ""
                ok, msg = self.event_mgr.delete_event(event_id)
                status = 200 if ok else 404
                self._send_json(status, {"status": "success" if ok else "error", "message": msg})
                return

            elif path == "/api/route/evaluate":
                orig = body.get("origin_road") or "RD_BLR_01"
                dest = body.get("destination_road") or "RD_BLR_04"
                date = body.get("date") or "2026-03-18"
                time_str = body.get("time") or "09:00"
                evaluation = self.navigator.evaluate_route(orig, dest, date, time_str)
                eval_dict = evaluation.to_dict()
                self._send_json(200, {"status": "success", "evaluation": eval_dict})
                return

            elif path == "/api/junction/telemetry":
                road_id = body.get("road_id", "RD_BLR_01")
                time_str = body.get("time", "17:00")
                date_str = body.get("date", "2026-03-18")
                is_rerouted = bool(body.get("is_rerouted", False))
                alt_road = body.get("alternate_road", None)
                hour, minute = parse_time_str(time_str)
                telemetry = self.junction_service.get_junction_telemetry(
                    road_id=road_id,
                    hour=hour,
                    minute=minute,
                    is_rerouted=is_rerouted,
                    alternate_road_id=alt_road,
                    date_str=date_str
                )
                self._send_json(200, {"status": "success", "junction": telemetry})
                return

            elif path == "/api/simulation/run":
                zone = body.get("zone", None)
                alpha = float(body.get("alpha", 0.20))
                beta = float(body.get("beta", 0.10))
                hour = int(body.get("hour", 17))
                day_of_week = int(body.get("day_of_week", 3))
                result = self.simulator.simulate_zone_policy(zone, alpha, beta, hour, day_of_week)
                self._send_json(200, {"status": "success", "simulation": result})
                return

            elif path == "/api/predict/explain":
                features = body.get("features", {})
                result = self.predictor.predict_segment(features, explain=True)
                self._send_json(200, {"status": "success", "explanation": result})
                return

            self._send_json(404, {"error": f"Endpoint '{path}' not found"})
        except Exception as e:
            self._send_json(500, {"status": "error", "message": f"Server error: {str(e)}", "code": 500})

def run_server(port: int = 8080, predictor: Optional[TrafficPredictor] = None, event_mgr: Optional[EventManager] = None):
    TrafficAppServer.security = SecurityManager()
    TrafficAppServer.event_mgr = event_mgr if event_mgr is not None else EventManager()
    if predictor is not None:
        TrafficAppServer.predictor = predictor
    else:
        TrafficAppServer.predictor = TrafficPredictor()
        TrafficAppServer.predictor.load_artifacts()

    TrafficAppServer.navigator = RouteNavigator(TrafficAppServer.predictor, TrafficAppServer.event_mgr)
    TrafficAppServer.simulator = PolicySimulator(TrafficAppServer.predictor, TrafficAppServer.event_mgr)
    TrafficAppServer.junction_service = JunctionService(TrafficAppServer.predictor, TrafficAppServer.event_mgr)

    server = ThreadingHTTPServer(("0.0.0.0", port), TrafficAppServer)
    print(f"=================================================================")
    print(f" Traffic AI High-Performance Threading Server Live on http://localhost:{port}")
    print(f" Commuter Navigator & Traffic Management Control Room Active")
    print(f"=================================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)

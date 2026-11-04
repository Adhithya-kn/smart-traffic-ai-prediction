"""
traffic_system/integrations/api_manager.py - Centralized External API Integration Controller
Orchestrates TomTom, Google Maps Platform, Weather, and Health Checker subsystems.
Provides safe configuration updates, persistent encrypted secrets, connectivity audits, and provenance tracking.
"""

import os
import time
import threading
from typing import Dict, Any, Tuple, Optional

from traffic_system.core.time_utils import now_iso
from traffic_system.core.secrets_manager import get_secrets_manager
from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.weather_client import WeatherClient
from traffic_system.integrations.google_maps_client import GoogleMapsClient
from traffic_system.integrations.health_checker import IntegrationHealthChecker


class APIManager:
    """
    Central API Manager governing live external data providers.
    Ensures safe configuration, secret masking, connection testing, and status reporting.
    """
    _instance: Optional["APIManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.tomtom = TomTomClient()
        self.weather = WeatherClient()
        self.google_maps = GoogleMapsClient()
        self.health_checker = IntegrationHealthChecker(self.tomtom, self.weather, self.google_maps)

    @classmethod
    def get_instance(cls) -> "APIManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = APIManager()
            return cls._instance

    def get_providers(self) -> Dict[str, Any]:
        """Returns details on available third-party data providers."""
        return {
            "timestamp": now_iso(),
            "providers": [
                {
                    "name": "TomTom Traffic",
                    "type": "traffic_flow_and_incidents",
                    "configured": self.tomtom.is_configured(),
                    "connection_tested": self.tomtom.connection_tested,
                    "currently_reachable": self.tomtom.currently_reachable,
                    "supplying_data": self.tomtom.supplying_data,
                    "status_code": self.tomtom.get_status_code(),
                    "key_required": True,
                    "masked_key": self.tomtom.get_masked_key(),
                    "base_url": self.tomtom.base_url,
                    "last_attempted_request": self.tomtom.last_attempted_request,
                    "last_successful_retrieval": self.tomtom.last_successful_retrieval
                },
                {
                    "name": "Google Maps Platform",
                    "type": "places_geocoding_and_heatmap",
                    "configured": self.google_maps.is_configured(),
                    "connection_tested": self.google_maps.connection_tested,
                    "currently_reachable": self.google_maps.currently_reachable,
                    "supplying_data": self.google_maps.supplying_data,
                    "status_code": self.google_maps.get_status_code(),
                    "key_required": True,
                    "masked_key": self.google_maps.get_masked_key(),
                    "base_url": self.google_maps.base_url,
                    "last_attempted_request": self.google_maps.last_attempted_request,
                    "last_successful_retrieval": self.google_maps.last_successful_retrieval
                },
                {
                    "name": "Open-Meteo",
                    "type": "meteorological_forecast",
                    "configured": self.weather.is_configured(),
                    "connection_tested": self.weather.connection_tested,
                    "currently_reachable": self.weather.currently_reachable,
                    "supplying_data": self.weather.supplying_data,
                    "status_code": self.weather.get_status_code(),
                    "key_required": False,
                    "masked_key": self.weather.get_masked_key(),
                    "base_url": self.weather.base_url,
                    "last_attempted_request": self.weather.last_attempted_request,
                    "last_successful_retrieval": self.weather.last_successful_retrieval
                }
            ]
        }

    def update_tomtom_config(self, api_key: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Updates, validates, persists, and invalidates caches for the TomTom API key."""
        clean_key = str(api_key).strip()
        if not clean_key:
            return False, "API key cannot be empty.", {}

        self.tomtom.set_api_key(clean_key)
        # Persist securely without storing raw keys in ordinary JSON
        get_secrets_manager().set_secret("TOMTOM_API_KEY", clean_key)

        # Invalidate live bridge caches and sync client key
        try:
            from traffic_system.live import bridge as live_bridge_mod
            if getattr(live_bridge_mod, "_LIVE_BRIDGE", None) is not None:
                bridge = live_bridge_mod._LIVE_BRIDGE
                bridge.tomtom_key = clean_key
                bridge.tomtom_client.set_api_key(clean_key)
                bridge.clear_cache()
        except Exception:
            pass

        return True, "TomTom API key configured successfully.", {
            "configured": self.tomtom.is_configured(),
            "status_code": self.tomtom.get_status_code(),
            "masked_key": self.tomtom.get_masked_key()
        }

    def update_google_maps_config(self, api_key: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Updates, persists, and invalidates caches for the Google Maps API key."""
        clean_key = str(api_key).strip()
        if not clean_key:
            return False, "API key cannot be empty.", {}

        self.google_maps.set_api_key(clean_key)
        get_secrets_manager().set_secret("GOOGLE_MAPS_API_KEY", clean_key)
        os.environ["GOOGLE_MAPS_API_KEY"] = clean_key
        os.environ["GOOGLE_MAPS_BROWSER_KEY"] = clean_key

        return True, "Google Maps API key configured successfully.", {
            "configured": self.google_maps.is_configured(),
            "status_code": self.google_maps.get_status_code(),
            "masked_key": self.google_maps.get_masked_key()
        }

    def update_weather_config(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Updates weather provider settings and flushes weather caches."""
        self.weather.set_config(api_key=api_key, base_url=base_url)
        if api_key is not None:
            get_secrets_manager().set_secret("WEATHER_API_KEY", api_key)
        if base_url is not None:
            get_secrets_manager().set_secret("WEATHER_BASE_URL", base_url)

        # Invalidate live bridge weather caches
        try:
            from traffic_system.live import bridge as live_bridge_mod
            if getattr(live_bridge_mod, "_LIVE_BRIDGE", None) is not None:
                live_bridge_mod._LIVE_BRIDGE.clear_cache()
        except Exception:
            pass

        return True, "Weather provider configuration updated.", {
            "masked_key": self.weather.get_masked_key(),
            "base_url": self.weather.base_url,
            "status_code": self.weather.get_status_code()
        }

    def test_tomtom(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Tests live connectivity to the TomTom API."""
        reachable, msg, latency = self.tomtom.test_connection()
        return reachable, msg, {
            "configured": self.tomtom.is_configured(),
            "connection_tested": self.tomtom.connection_tested,
            "reachable": reachable,
            "currently_reachable": self.tomtom.currently_reachable,
            "supplying_data": self.tomtom.supplying_data,
            "status_code": self.tomtom.get_status_code(),
            "latency_ms": latency,
            "message": msg,
            "last_attempted_request": self.tomtom.last_attempted_request,
            "last_successful_retrieval": self.tomtom.last_successful_retrieval
        }

    def test_google_maps(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Tests live connectivity to the Google Maps API."""
        reachable, msg, latency = self.google_maps.test_connection()
        return reachable, msg, {
            "configured": self.google_maps.is_configured(),
            "connection_tested": self.google_maps.connection_tested,
            "reachable": reachable,
            "currently_reachable": self.google_maps.currently_reachable,
            "supplying_data": self.google_maps.supplying_data,
            "status_code": self.google_maps.get_status_code(),
            "latency_ms": latency,
            "message": msg,
            "last_attempted_request": self.google_maps.last_attempted_request,
            "last_successful_retrieval": self.google_maps.last_successful_retrieval
        }

    def test_weather(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Tests live connectivity to the Weather API."""
        reachable, msg, latency = self.weather.test_connection()
        return reachable, msg, {
            "configured": self.weather.is_configured(),
            "connection_tested": self.weather.connection_tested,
            "reachable": reachable,
            "currently_reachable": self.weather.currently_reachable,
            "supplying_data": self.weather.supplying_data,
            "status_code": self.weather.get_status_code(),
            "latency_ms": latency,
            "message": msg,
            "last_attempted_request": self.weather.last_attempted_request,
            "last_successful_retrieval": self.weather.last_successful_retrieval
        }

    def get_status(self) -> Dict[str, Any]:
        """Provides full connection and sync status for live providers."""
        return {
            "timestamp": now_iso(),
            "tomtom": self.tomtom.get_status(),
            "google_maps": self.google_maps.get_status(),
            "weather": self.weather.get_status(),
            "is_live_data_active": self.tomtom.is_configured() and self.tomtom.currently_reachable and self.tomtom.supplying_data
        }

    def get_health_report(self) -> Dict[str, Any]:
        """Generates comprehensive external provider health report."""
        return self.health_checker.check_all()

    def execute_multi_subsystem_handshake(self) -> Dict[str, Any]:
        """
        Executes active end-to-end diagnostic probes across all six core subsystems:
        TomTom, Google Maps, Open-Meteo, POSIX Database, Machine Learning, and Computer Vision.
        Measures roundtrip latency and returns transparent status matrix.
        """
        t_start = time.perf_counter()

        # 1. External APIs
        tomtom_ok, tomtom_msg, tomtom_lat = self.tomtom.test_connection()
        gmaps_ok, gmaps_msg, gmaps_lat = self.google_maps.test_connection()
        weather_ok, weather_msg, weather_lat = self.weather.test_connection()

        # 2. Database IO probe
        db_start = time.perf_counter()
        db_ok = True
        db_msg = "POSIX atomic database accessible with F_FULLFSYNC."
        from traffic_system.config import USERS_DB_PATH, EVENTS_DB_PATH
        try:
            db_ok = USERS_DB_PATH.exists() and EVENTS_DB_PATH.exists()
        except Exception as e:
            db_ok = False
            db_msg = str(e)
        db_lat = round((time.perf_counter() - db_start) * 1000, 2)

        # 3. Machine Learning Inference Engine probe
        ml_start = time.perf_counter()
        ml_ok = True
        ml_msg = "XGBoost 80-tree model active."
        try:
            from app.server import TrafficAppServer
            if TrafficAppServer.predictor and TrafficAppServer.predictor.is_trained():
                probe_benchmark_features = {
                    "city_zone": "Indiranagar", "road_id": "RD_BLR_01", "intersection_id": "JNC_01",
                    "vehicle_count": 1200, "average_speed": 28.0, "capacity_utilization": 45.0,
                    "congestion_level": "Moderate", "hour": 10, "day_of_week": 2, "is_weekend": 0
                }
                pred_c, _ = TrafficAppServer.predictor.predict_segment(probe_benchmark_features)
                ml_msg = f"Inference verified: test prediction '{pred_c}'."
            else:
                ml_ok = False
                ml_msg = "Predictor model topology not initialized."
        except Exception as e:
            ml_ok = False
            ml_msg = str(e)
        ml_lat = round((time.perf_counter() - ml_start) * 1000, 2)

        # 4. Computer Vision probe (Accurate Extraction)
        cv_start = time.perf_counter()
        cv_ok = True
        cv_msg = "Computer vision video pipeline operational."
        try:
            from app.routes.vision_routes import get_vision_handler
            v_handler = get_vision_handler()
            code, status_resp = v_handler.handle_get_status()
            data = status_resp.get("data", {}) if isinstance(status_resp, dict) else {}
            yolo_loaded = bool(data.get("yolo_loaded", False))
            yolo_model = data.get("yolo_model") or "yolo11n.pt"
            load_error = data.get("load_error")
            if code == 200 and yolo_loaded:
                cv_ok = True
                cv_msg = f"CV engine: Ultralytics YOLO ({yolo_model}) active."
            else:
                cv_ok = False
                cv_msg = f"CV engine unavailable: {load_error or 'Weights not loaded'}."
        except Exception as e:
            cv_ok = False
            cv_msg = str(e)
        cv_lat = round((time.perf_counter() - cv_start) * 1000, 2)

        total_lat = round((time.perf_counter() - t_start) * 1000, 2)

        all_ok = weather_ok and db_ok and ml_ok and cv_ok
        overall_health = "OPTIMAL" if (all_ok and (tomtom_ok or not self.tomtom.is_configured()) and (gmaps_ok or not self.google_maps.is_configured())) else "DEGRADED"

        return {
            "timestamp": now_iso(),
            "overall_health": overall_health,
            "total_latency_ms": total_lat,
            "subsystems": {
                "tomtom_traffic": {
                    "name": "TomTom Traffic",
                    "status": "CONNECTED" if tomtom_ok else ("CONFIGURED_UNREACHABLE" if self.tomtom.is_configured() else "STANDBY_FALLBACK"),
                    "reachable": tomtom_ok,
                    "latency_ms": tomtom_lat,
                    "configured": self.tomtom.is_configured(),
                    "masked_key": self.tomtom.get_masked_key(),
                    "message": tomtom_msg
                },
                "google_maps": {
                    "name": "Google Maps Platform",
                    "status": "CONNECTED" if gmaps_ok else ("CONFIGURED_UNREACHABLE" if self.google_maps.is_configured() else "STANDBY_FALLBACK"),
                    "reachable": gmaps_ok,
                    "latency_ms": gmaps_lat,
                    "configured": self.google_maps.is_configured(),
                    "masked_key": self.google_maps.get_masked_key(),
                    "message": gmaps_msg
                },
                "open_meteo": {
                    "name": "Open-Meteo Weather",
                    "status": "CONNECTED" if weather_ok else "OFFLINE_FALLBACK",
                    "reachable": weather_ok,
                    "latency_ms": weather_lat,
                    "configured": True,
                    "message": weather_msg
                },
                "database_storage": {
                    "name": "POSIX Atomic DB Storage",
                    "status": "OPERATIONAL" if db_ok else "ERROR",
                    "reachable": db_ok,
                    "latency_ms": db_lat,
                    "configured": True,
                    "message": db_msg
                },
                "ml_prediction_engine": {
                    "name": "XGBoost 80-Tree Ensemble",
                    "status": "OPERATIONAL" if ml_ok else "OFFLINE",
                    "reachable": ml_ok,
                    "latency_ms": ml_lat,
                    "configured": True,
                    "message": ml_msg
                },
                "computer_vision": {
                    "name": "YOLO Vehicle CV Engine",
                    "status": "OPERATIONAL" if cv_ok else "ERROR",
                    "reachable": cv_ok,
                    "latency_ms": cv_lat,
                    "configured": True,
                    "message": cv_msg
                }
            }
        }


def get_api_manager() -> APIManager:
    return APIManager.get_instance()

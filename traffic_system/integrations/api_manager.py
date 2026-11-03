"""
traffic_system/integrations/api_manager.py - Centralized External API Integration Controller
Orchestrates TomTom, Weather, and Health Checker subsystems.
Provides safe configuration updates, connectivity audits, and provenance tracking.
"""

import threading
from typing import Dict, Any, Tuple, Optional

from traffic_system.core.time_utils import now_iso
from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.weather_client import WeatherClient
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
        self.health_checker = IntegrationHealthChecker(self.tomtom, self.weather)

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
                    "key_required": True,
                    "masked_key": self.tomtom.get_masked_key(),
                    "base_url": self.tomtom.base_url,
                    "last_successful_retrieval": self.tomtom.last_successful_retrieval
                },
                {
                    "name": "Open-Meteo",
                    "type": "meteorological_forecast",
                    "configured": True,
                    "key_required": False,
                    "masked_key": self.weather.get_masked_key(),
                    "base_url": self.weather.base_url,
                    "last_successful_retrieval": self.weather.last_successful_retrieval
                }
            ]
        }

    def update_tomtom_config(self, api_key: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Updates and validates the TomTom API key."""
        clean_key = str(api_key).strip()
        if not clean_key:
            return False, "API key cannot be empty.", {}

        self.tomtom.set_api_key(clean_key)
        
        # Also update bridge singleton if initialized
        try:
            from traffic_system.live.bridge import get_live_bridge
            bridge = get_live_bridge()
            bridge.tomtom_key = clean_key
            bridge.clear_cache()
        except Exception:
            pass

        return True, "TomTom API key configured successfully.", {
            "configured": self.tomtom.is_configured(),
            "masked_key": self.tomtom.get_masked_key()
        }

    def update_weather_config(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Updates weather provider settings."""
        self.weather.set_config(api_key=api_key, base_url=base_url)
        return True, "Weather provider configuration updated.", {
            "masked_key": self.weather.get_masked_key(),
            "base_url": self.weather.base_url
        }

    def test_tomtom(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Tests live connectivity to the TomTom API."""
        reachable, msg, latency = self.tomtom.test_connection()
        return reachable, msg, {
            "reachable": reachable,
            "latency_ms": latency,
            "message": msg,
            "last_successful_retrieval": self.tomtom.last_successful_retrieval
        }

    def test_weather(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Tests live connectivity to the Weather API."""
        reachable, msg, latency = self.weather.test_connection()
        return reachable, msg, {
            "reachable": reachable,
            "latency_ms": latency,
            "message": msg,
            "last_successful_retrieval": self.weather.last_successful_retrieval
        }

    def get_status(self) -> Dict[str, Any]:
        """Provides full connection and sync status for live providers."""
        return {
            "timestamp": now_iso(),
            "tomtom": self.tomtom.get_status(),
            "weather": self.weather.get_status(),
            "is_live_data_active": self.tomtom.is_configured() and self.tomtom.last_error is None
        }


def get_api_manager() -> APIManager:
    return APIManager.get_instance()

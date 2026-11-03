"""
traffic_system/integrations/health_checker.py - Third-Party API Health Verification Service
Runs active diagnostics against external TomTom and Weather providers.
"""

from typing import Dict, Any, Tuple
from traffic_system.core.time_utils import now_iso
from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.weather_client import WeatherClient


class IntegrationHealthChecker:
    """Performs deep health and connectivity audits of third-party telemetry services."""
    def __init__(self, tomtom_client: TomTomClient, weather_client: WeatherClient):
        self.tomtom = tomtom_client
        self.weather = weather_client

    def check_all(self) -> Dict[str, Any]:
        """
        Executes end-to-end connectivity test for all external providers.
        Returns comprehensive structured report.
        """
        tomtom_ok, tomtom_msg, tomtom_latency = self.tomtom.test_connection()
        weather_ok, weather_msg, weather_latency = self.weather.test_connection()

        return {
            "timestamp": now_iso(),
            "tomtom": {
                "configured": self.tomtom.is_configured(),
                "reachable": tomtom_ok,
                "message": tomtom_msg,
                "latency_ms": tomtom_latency,
                "last_successful_retrieval": self.tomtom.last_successful_retrieval,
                "masked_key": self.tomtom.get_masked_key()
            },
            "weather": {
                "configured": True,  # Open-Meteo does not require key
                "reachable": weather_ok,
                "message": weather_msg,
                "latency_ms": weather_latency,
                "last_successful_retrieval": self.weather.last_successful_retrieval,
                "masked_key": self.weather.get_masked_key()
            },
            "summary": {
                "all_healthy": weather_ok and (tomtom_ok or not self.tomtom.is_configured()),
                "live_traffic_active": tomtom_ok,
                "live_weather_active": weather_ok
            }
        }

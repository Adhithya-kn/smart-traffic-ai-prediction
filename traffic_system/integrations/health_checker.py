"""
traffic_system/integrations/health_checker.py - Third-Party API Health Verification Service
Runs active diagnostics against external TomTom, Google Maps Platform, and Weather providers.
"""

from typing import Dict, Any, Optional
from traffic_system.core.time_utils import now_iso
from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.weather_client import WeatherClient
from traffic_system.integrations.google_maps_client import GoogleMapsClient


class IntegrationHealthChecker:
    """Performs deep health and connectivity audits of third-party telemetry services."""
    def __init__(
        self,
        tomtom_client: TomTomClient,
        weather_client: WeatherClient,
        google_maps_client: Optional[GoogleMapsClient] = None
    ):
        self.tomtom = tomtom_client
        self.weather = weather_client
        self.google_maps = google_maps_client or GoogleMapsClient()

    def check_all(self) -> Dict[str, Any]:
        """
        Executes end-to-end connectivity test for all external providers.
        Returns comprehensive structured report including TomTom, Google Maps, and Open-Meteo.
        """
        tomtom_ok, tomtom_msg, tomtom_latency = self.tomtom.test_connection()
        weather_ok, weather_msg, weather_latency = self.weather.test_connection()
        gmaps_ok, gmaps_msg, gmaps_latency = self.google_maps.test_connection()

        return {
            "timestamp": now_iso(),
            "tomtom": {
                "configured": self.tomtom.is_configured(),
                "connection_tested": self.tomtom.connection_tested,
                "reachable": tomtom_ok,
                "currently_reachable": self.tomtom.currently_reachable,
                "supplying_data": self.tomtom.supplying_data,
                "status_code": self.tomtom.get_status_code(),
                "message": tomtom_msg,
                "latency_ms": tomtom_latency,
                "last_attempted_request": self.tomtom.last_attempted_request,
                "last_successful_retrieval": self.tomtom.last_successful_retrieval,
                "masked_key": self.tomtom.get_masked_key()
            },
            "google_maps": {
                "configured": self.google_maps.is_configured(),
                "connection_tested": self.google_maps.connection_tested,
                "reachable": gmaps_ok,
                "currently_reachable": self.google_maps.currently_reachable,
                "supplying_data": self.google_maps.supplying_data,
                "status_code": self.google_maps.get_status_code(),
                "message": gmaps_msg,
                "latency_ms": gmaps_latency,
                "last_attempted_request": self.google_maps.last_attempted_request,
                "last_successful_retrieval": self.google_maps.last_successful_retrieval,
                "masked_key": self.google_maps.get_masked_key()
            },
            "weather": {
                "configured": self.weather.is_configured(),
                "connection_tested": self.weather.connection_tested,
                "reachable": weather_ok,
                "currently_reachable": self.weather.currently_reachable,
                "supplying_data": self.weather.supplying_data,
                "status_code": self.weather.get_status_code(),
                "message": weather_msg,
                "latency_ms": weather_latency,
                "last_attempted_request": self.weather.last_attempted_request,
                "last_successful_retrieval": self.weather.last_successful_retrieval,
                "masked_key": self.weather.get_masked_key()
            },
            "summary": {
                "all_healthy": weather_ok and (tomtom_ok or not self.tomtom.is_configured()) and (gmaps_ok or not self.google_maps.is_configured()),
                "live_traffic_active": tomtom_ok and self.tomtom.supplying_data,
                "live_weather_active": weather_ok and self.weather.supplying_data,
                "google_maps_active": gmaps_ok
            }
        }

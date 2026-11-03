"""
traffic_system/integrations - External API Integration Subsystem
Provides hardened, resilient interfaces for TomTom Traffic and Open-Meteo services.
"""

from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.weather_client import WeatherClient
from traffic_system.integrations.health_checker import IntegrationHealthChecker
from traffic_system.integrations.api_manager import APIManager, get_api_manager

__all__ = [
    "TomTomClient",
    "WeatherClient",
    "IntegrationHealthChecker",
    "APIManager",
    "get_api_manager",
]

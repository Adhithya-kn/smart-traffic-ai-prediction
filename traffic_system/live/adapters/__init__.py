"""
traffic_system/live/adapters - Third-Party API Adapters (Adapter Pattern).
"""

from .base import CorridorObservation, WeatherSnapshot, ITelemetryAdapter, IWeatherAdapter

__all__ = ["CorridorObservation", "WeatherSnapshot", "ITelemetryAdapter", "IWeatherAdapter"]

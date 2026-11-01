"""
traffic_system/live/adapters/base.py - Domain Entities & Adapter Interfaces (Adapter Pattern).
Normalizes third-party vendor schemas into immutable domain snapshots.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class CorridorObservation:
    """Standardized internal telemetry representation."""
    road_id: str
    road_name: str
    city_zone: str
    intersection_name: str
    current_speed: float
    free_flow_speed: float
    speed_performance_index: float
    congestion_level: str
    capacity_utilization: float
    vehicle_count: int
    design_capacity: int
    confidence: float
    is_road_closed: bool
    is_live: bool
    source: str
    timestamp: str

@dataclass(frozen=True)
class WeatherSnapshot:
    """Standardized internal meteorological state."""
    condition: str
    temperature: float
    precipitation_mm: float
    weather_code: int
    is_live: bool
    source: str

class ITelemetryAdapter(ABC):
    """Normalizes raw GPS probe payloads into CorridorObservation."""
    @abstractmethod
    def adapt_flow(self, raw_flow: Dict[str, Any], corridor_meta: Dict[str, Any], baseline_data: Dict[str, Any]) -> CorridorObservation:
        pass

class IWeatherAdapter(ABC):
    """Normalizes raw weather API payloads into WeatherSnapshot."""
    @abstractmethod
    def adapt_weather(self, raw_weather: Dict[str, Any]) -> WeatherSnapshot:
        pass

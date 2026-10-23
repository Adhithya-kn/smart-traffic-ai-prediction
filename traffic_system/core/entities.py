"""
traffic_system/core/entities.py - Domain Models and Data Structures
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime

class CongestionLevel(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    SEVERE = "Severe"

class UserRole(str, Enum):
    ROAD_USER = "Road User"
    TRAFFIC_MANAGEMENT = "Traffic Management"
    COMMUTER = "Road User"
    TRAFFIC_AUTHORITY = "Traffic Management"

class EventType(str, Enum):
    ROADWORK = "Roadwork & Maintenance"
    STADIUM_EVENT = "Stadium / Concert Event"
    FESTIVAL = "Cultural Festival / Procession"
    SEVERE_WEATHER = "Severe Weather Alert"
    VIP_MOVEMENT = "VIP Movement / Escort"
    ACCIDENT = "Accident / Collision"

@dataclass
class TrafficEvent:
    id: str
    name: str
    event_type: str
    city_zone: str
    affected_roads: List[str]
    start_time: str  # ISO string or HH:MM
    end_time: str
    date: str        # YYYY-MM-DD
    severity_boost: int  # 1 to 3 steps increase in congestion rank
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RoadSegment:
    road_id: str
    intersection_id: str
    city_zone: str
    speed_limit: int
    lanes: int
    base_speed: float
    base_volume: int
    current_congestion: CongestionLevel
    predicted_congestion: CongestionLevel
    road_name: str = ""
    intersection_name: str = ""
    active_events: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["current_congestion"] = self.current_congestion.value
        d["predicted_congestion"] = self.predicted_congestion.value
        return d

@dataclass
class RouteEvaluation:
    origin_road: str
    destination_road: str
    date: str
    time: str
    city_zone: str
    primary_route: List[str]
    primary_congestion: str
    is_rerouted: bool
    recommended_route: List[str]
    recommended_congestion: str
    time_saved_minutes: float
    active_events: List[Dict[str, Any]]
    recommendation_narrative: str
    expected_vehicle_count: int = 0
    corridor_speed_kmh: float = 0.0
    alternate_vehicle_count: int = 0
    alternate_speed_kmh: float = 0.0
    origin_road_name: str = ""
    destination_road_name: str = ""
    primary_route_names: List[str] = field(default_factory=list)
    recommended_route_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

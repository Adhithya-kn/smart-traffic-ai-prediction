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

CONGESTION_RANKS: Dict[str, int] = {"Low": 0, "Moderate": 1, "High": 2, "Severe": 3}
RANK_TO_CONGESTION: Dict[int, str] = {0: "Low", 1: "Moderate", 2: "High", 3: "Severe"}

def congestion_rank(level: str) -> int:
    """Returns numerical rank 0-3 for a given congestion level."""
    return CONGESTION_RANKS.get(str(level).strip().capitalize(), 1)

def rank_to_congestion(rank: int) -> str:
    """Returns congestion string level ('Low' to 'Severe') for an integer rank."""
    return RANK_TO_CONGESTION.get(max(0, min(3, int(rank))), "Moderate")

def make_feature_vector(
    road_id: str,
    vehicle_count: int,
    average_speed: float,
    capacity_utilization: float,
    congestion_level: str,
    hour: int,
    day_of_week: int,
    is_weekend: int,
    city_zone: str = "Indiranagar",
    intersection_id: str = ""
) -> Dict[str, Any]:
    """Standardized factory constructing XGBoost model input feature vectors (DRY)."""
    return {
        "road_id": road_id,
        "vehicle_count": int(vehicle_count),
        "average_speed": round(float(average_speed), 1),
        "capacity_utilization": round(float(capacity_utilization), 1),
        "congestion_level": str(congestion_level).strip().capitalize(),
        "hour": int(hour),
        "day_of_week": int(day_of_week),
        "is_weekend": int(is_weekend),
        "city_zone": city_zone,
        "intersection_id": intersection_id or f"INT_{road_id}"
    }

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

@dataclass(slots=True)
class TrafficEvent:
    id: str
    name: str
    event_type: str
    city_zone: str
    affected_roads: List[str]
    start_time: str
    end_time: str
    date: str
    severity_boost: int
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
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

@dataclass(slots=True)
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

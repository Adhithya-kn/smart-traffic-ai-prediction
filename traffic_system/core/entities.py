"""
traffic_system/core/entities.py - Domain Models and Data Structures
Standardizes domain entities, provenance markers, incident schemas, and route evaluations.
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
from traffic_system.core.time_utils import now_iso


class DataProvenance(str, Enum):
    HISTORICAL_DATASET = "Historical dataset"
    TOMTOM_LIVE_API = "TomTom live API"
    OPEN_METEO_LIVE_API = "Open-Meteo live API"
    CACHED_API_RESPONSE = "Cached API response"
    SAMPLE_VIDEO_ANALYSIS = "Sample-video analysis"
    GENUINE_YOLO_INFERENCE = "Genuine YOLO inference"
    SIMULATION = "Simulation"
    EMPIRICAL_BASELINE = "Empirical Live Baseline"


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
    OPERATOR = "Traffic Management"
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
    source_name: str = ""
    source_url: str = ""
    publication_date: str = ""
    verification_date: str = ""
    verification_status: str = "OFFICIAL_VERIFIED"
    provenance: str = DataProvenance.HISTORICAL_DATASET.value
    observation_time: str = field(default_factory=now_iso)
    retrieved_time: str = field(default_factory=now_iso)
    is_published: bool = False
    is_historical: bool = False

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
    provenance: str = DataProvenance.HISTORICAL_DATASET.value
    observation_time: str = field(default_factory=now_iso)
    retrieved_time: str = field(default_factory=now_iso)

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
    primary_travel_time_minutes: float = 0.0
    recommended_travel_time_minutes: float = 0.0
    departure_date: str = ""
    departure_time: str = ""
    is_historical_model_estimate: bool = True
    origin_road_name: str = ""
    destination_road_name: str = ""
    primary_route_names: List[str] = field(default_factory=list)
    recommended_route_names: List[str] = field(default_factory=list)
    primary_lane_guidance: List[Dict[str, Any]] = field(default_factory=list)
    recommended_lane_guidance: List[Dict[str, Any]] = field(default_factory=list)
    primary_polylines: List[List[float]] = field(default_factory=list)
    recommended_polylines: List[List[float]] = field(default_factory=list)
    provenance: str = DataProvenance.SIMULATION.value
    observation_time: str = field(default_factory=now_iso)
    retrieved_time: str = field(default_factory=now_iso)
    estimated_time_saved_minutes: float = 0.0
    is_simulated: bool = True
    disclaimer: str = (
        "Route travel times, alternate paths and estimated time savings are simulated model "
        "estimates based on topological network models, not field-verified guarantees."
    )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not d.get("estimated_time_saved_minutes"):
            d["estimated_time_saved_minutes"] = d.get("time_saved_minutes", 0.0)
        return d


@dataclass(slots=True)
class ProviderStatus:
    provider: str
    configured: bool
    reachable: bool
    status_code: int
    latency_ms: float
    last_successful_retrieval: Optional[str]
    error_message: Optional[str]
    provenance: str
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

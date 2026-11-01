"""
traffic_system/core/road_registry.py - Canonical Urban Road & Intersection Registry
Provides ground-truth road names, intersection cross-streets, and corridor types
for all 16 urban corridors across the 8 Bangalore metropolitan zones.
"""

from typing import Dict, Any, Optional

# Active Canonical Road Registry for the 16 corridors across 8 metropolitan zones
ROAD_REGISTRY: Dict[str, Dict[str, Any]] = {
    "RD_BLR_01": {
        "global_name": "100 Feet Road",
        "bangalore_name": "100 Feet Road",
        "road_type": "Primary Commercial Arterial",
        "intersection_name": "CMH Road Junction",
        "intersection_id": "INT_BLR_05",
        "city_zone": "Indiranagar",
    },
    "RD_BLR_02": {
        "global_name": "Anil Kumble Circle",
        "bangalore_name": "Anil Kumble Circle",
        "road_type": "CBD Commercial Intersection",
        "intersection_name": "Anil Kumble Crossing",
        "intersection_id": "INT_BLR_03",
        "city_zone": "M.G. Road CBD",
    },
    "RD_BLR_03": {
        "global_name": "Ballari Road",
        "bangalore_name": "Ballari Road",
        "road_type": "Airport Express Highway (NH-44)",
        "intersection_name": "Bellary Airport Toll Crossing",
        "intersection_id": "INT_BLR_04",
        "city_zone": "Hebbal North",
    },
    "RD_BLR_04": {
        "global_name": "CMH Road",
        "bangalore_name": "CMH Road",
        "road_type": "Metro Transit Arterial",
        "intersection_name": "100 Feet Road Junction",
        "intersection_id": "INT_BLR_01",
        "city_zone": "Indiranagar",
    },
    "RD_BLR_05": {
        "global_name": "Hebbal Flyover",
        "bangalore_name": "Hebbal Flyover",
        "road_type": "Multi-lane Cloverleaf Interchange",
        "intersection_name": "Hebbal Flyover Cloverleaf",
        "intersection_id": "INT_BLR_06",
        "city_zone": "Hebbal North",
    },
    "RD_BLR_06": {
        "global_name": "Hosur Road",
        "bangalore_name": "Hosur Road",
        "road_type": "Elevated Expressway Arterial",
        "intersection_name": "Hosur Road Expressway Gate",
        "intersection_id": "INT_BLR_08",
        "city_zone": "Electronic City South",
    },
    "RD_BLR_07": {
        "global_name": "ITPL Main Road",
        "bangalore_name": "ITPL Main Road",
        "road_type": "Technology Park Corridor",
        "intersection_name": "Hope Farm Crossing",
        "intersection_id": "INT_BLR_07",
        "city_zone": "Whitefield",
    },
    "RD_BLR_08": {
        "global_name": "Jayanagar 4th Block",
        "bangalore_name": "Jayanagar 4th Block",
        "road_type": "Commercial & Cultural Spine",
        "intersection_name": "4th Block Complex Gate",
        "intersection_id": "INT_BLR_02",
        "city_zone": "Jayanagar",
    },
    "RD_BLR_09": {
        "global_name": "Marathahalli Bridge",
        "bangalore_name": "Marathahalli Bridge",
        "road_type": "Multi-lane Bridge Interchange",
        "intersection_name": "Marathahalli Bridge Interchange",
        "intersection_id": "INT_BLR_09",
        "city_zone": "Whitefield",
    },
    "RD_BLR_10": {
        "global_name": "Sarjapur Road",
        "bangalore_name": "Sarjapur Road",
        "road_type": "High-Density Arterial Corridor",
        "intersection_name": "Sarjapur-Koramangala Link",
        "intersection_id": "INT_BLR_10",
        "city_zone": "Koramangala",
    },
    "RD_BLR_11": {
        "global_name": "Silk Board Junction",
        "bangalore_name": "Silk Board Junction",
        "road_type": "High-Capacity Flyover Interchange",
        "intersection_name": "Silk Board Interchange Flyover",
        "intersection_id": "INT_BLR_11",
        "city_zone": "Electronic City South",
    },
    "RD_BLR_12": {
        "global_name": "Sony World Junction",
        "bangalore_name": "Sony World Junction",
        "road_type": "Major 4-Way Retail Intersection",
        "intersection_name": "Sony World 4-Way Crossing",
        "intersection_id": "INT_BLR_12",
        "city_zone": "Koramangala",
    },
    "RD_BLR_13": {
        "global_name": "South End Circle",
        "bangalore_name": "South End Circle",
        "road_type": "Major 5-Way Rotary Intersection",
        "intersection_name": "South End 5-Way Rotary",
        "intersection_id": "INT_BLR_13",
        "city_zone": "Jayanagar",
    },
    "RD_BLR_14": {
        "global_name": "Trinity Circle",
        "bangalore_name": "Trinity Circle",
        "road_type": "Metro CBD Rotary Interchange",
        "intersection_name": "Trinity Circle Rotary",
        "intersection_id": "INT_BLR_14",
        "city_zone": "M.G. Road CBD",
    },
    "RD_BLR_15": {
        "global_name": "Tumkur Road",
        "bangalore_name": "Tumkur Road",
        "road_type": "National Highway Freight Corridor",
        "intersection_name": "Tumkur Highway Crossing",
        "intersection_id": "INT_BLR_15",
        "city_zone": "Yeshwanthpur West",
    },
    "RD_BLR_16": {
        "global_name": "Yeshwanthpur Circle",
        "bangalore_name": "Yeshwanthpur Circle",
        "road_type": "Multi-Modal Transit Junction",
        "intersection_name": "Yeshwanthpur Circle Rotary",
        "intersection_id": "INT_BLR_16",
        "city_zone": "Yeshwanthpur West",
    },
    "RD_BLR_17": {
        "global_name": "Old Airport Road",
        "bangalore_name": "Old Airport Road",
        "road_type": "Primary Arterial Corridor",
        "intersection_name": "Domlur Flyover Junction",
        "intersection_id": "INT_BLR_17",
        "city_zone": "Indiranagar",
    },
    "RD_BLR_18": {
        "global_name": "Brigade Road",
        "bangalore_name": "Brigade Road",
        "road_type": "Commercial Pedestrian & Arterial Spine",
        "intersection_name": "Residency Road Junction",
        "intersection_id": "INT_BLR_18",
        "city_zone": "M.G. Road CBD",
    },
    "RD_BLR_19": {
        "global_name": "Thanisandra Main Road",
        "bangalore_name": "Thanisandra Main Road",
        "road_type": "North Growth Corridor",
        "intersection_name": "Nagavara Junction Crossing",
        "intersection_id": "INT_BLR_19",
        "city_zone": "Hebbal North",
    },
    "RD_BLR_20": {
        "global_name": "Electronic City Phase 1",
        "bangalore_name": "Electronic City Phase 1",
        "road_type": "Tech Hub Arterial Spine",
        "intersection_name": "Toll Plaza Interchange",
        "intersection_id": "INT_BLR_20",
        "city_zone": "Electronic City South",
    },
    "RD_BLR_21": {
        "global_name": "Varthur Road",
        "bangalore_name": "Varthur Road",
        "road_type": "East Perimeter Transit Link",
        "intersection_name": "Kundalahalli Gate Crossing",
        "intersection_id": "INT_BLR_21",
        "city_zone": "Whitefield",
    },
    "RD_BLR_22": {
        "global_name": "Kanakapura Road",
        "bangalore_name": "Kanakapura Road",
        "road_type": "National Highway Transit Link",
        "intersection_name": "Sarakki Signal Junction",
        "intersection_id": "INT_BLR_22",
        "city_zone": "Jayanagar",
    },
    "RD_BLR_23": {
        "global_name": "Koramangala 80 Feet Road",
        "bangalore_name": "Koramangala 80 Feet Road",
        "road_type": "Major Commercial Link",
        "intersection_name": "National Games Village Crossing",
        "intersection_id": "INT_BLR_23",
        "city_zone": "Koramangala",
    },
    "RD_BLR_24": {
        "global_name": "Malleshwaram 8th Cross",
        "bangalore_name": "Malleshwaram 8th Cross",
        "road_type": "Historic Transit Arterial",
        "intersection_name": "Margosa Road Junction",
        "intersection_id": "INT_BLR_24",
        "city_zone": "Yeshwanthpur West",
    },
}

# Pre-indexed $O(1)$ intersection name map (eliminates O(N) linear scans across registry)
_INTERSECTION_NAME_MAP: Dict[str, str] = {
    info["intersection_id"]: info.get("intersection_name", info["intersection_id"])
    for info in ROAD_REGISTRY.values()
    if "intersection_id" in info
}

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import List

@dataclass(frozen=True)
class CorridorDefinition:
    """Unified Canonical Domain Entity for an Urban Corridor (Repository Pattern)."""
    road_id: str
    bangalore_name: str
    global_name: str
    city_zone: str
    road_type: str
    intersection_id: str
    intersection_name: str
    free_flow_speed: float = 50.0
    design_capacity: int = 55000

class IRoadRepository(ABC):
    """Abstract Repository interface for corridors and urban network topology."""
    @abstractmethod
    def get_by_id(self, road_id: str) -> Optional[CorridorDefinition]:
        pass

    @abstractmethod
    def list_all(self) -> List[CorridorDefinition]:
        pass

    @abstractmethod
    def list_by_zone(self, zone: str) -> List[CorridorDefinition]:
        pass

class CachedRoadRepository(IRoadRepository):
    """Thread-safe in-memory cached repository implementation."""
    def __init__(self):
        self._corridors: Dict[str, CorridorDefinition] = {}
        self._by_zone: Dict[str, List[CorridorDefinition]] = {}
        self._load()

    def _load(self):
        for r_id, info in ROAD_REGISTRY.items():
            defn = CorridorDefinition(
                road_id=r_id,
                bangalore_name=info.get("bangalore_name", r_id),
                global_name=info.get("global_name", r_id),
                city_zone=info.get("city_zone", "Indiranagar"),
                road_type=info.get("road_type", "Primary Arterial"),
                intersection_id=info.get("intersection_id", f"INT_{r_id}"),
                intersection_name=info.get("intersection_name", f"INT_{r_id}"),
                free_flow_speed=50.0,
                design_capacity=55000
            )
            self._corridors[r_id] = defn
            self._by_zone.setdefault(defn.city_zone.lower(), []).append(defn)

    def get_by_id(self, road_id: str) -> Optional[CorridorDefinition]:
        return self._corridors.get(road_id)

    def list_all(self) -> List[CorridorDefinition]:
        return list(self._corridors.values())

    def list_by_zone(self, zone: str) -> List[CorridorDefinition]:
        return list(self._by_zone.get(str(zone).strip().lower(), []))

_ROAD_REPO_INSTANCE: Optional[IRoadRepository] = None

def get_road_repository() -> IRoadRepository:
    global _ROAD_REPO_INSTANCE
    if _ROAD_REPO_INSTANCE is None:
        _ROAD_REPO_INSTANCE = CachedRoadRepository()
    return _ROAD_REPO_INSTANCE

def get_road_name(road_id: str, profile: str = "global") -> str:
    """Returns the human-readable road name for a given road_id."""
    info = ROAD_REGISTRY.get(road_id)
    if not info:
        return road_id
    return info.get("bangalore_name", info.get("global_name", road_id))

def get_intersection_name(intersection_id: str, profile: str = "global") -> str:
    """Returns the descriptive intersection name for an intersection_id using O(1) indexed lookup."""
    return _INTERSECTION_NAME_MAP.get(intersection_id, intersection_id)

def get_road_metadata(road_id: str, profile: str = "global") -> Dict[str, Any]:
    """Returns full metadata (road_name, intersection_name, road_type) for a road_id."""
    info = ROAD_REGISTRY.get(road_id, {})
    name = get_road_name(road_id, profile)
    int_name = info.get("intersection_name", info.get("intersection_id", ""))
    return {
        "road_id": road_id,
        "road_name": name,
        "road_type": info.get("road_type", "Urban Arterial Corridor"),
        "intersection_id": info.get("intersection_id", ""),
        "intersection_name": int_name,
        "city_zone": info.get("city_zone", "")
    }

def enrich_road_info(road_dict: Dict[str, Any], profile: str = "global") -> Dict[str, Any]:
    """Enriches a road dictionary with canonical road name and intersection details."""
    enriched = dict(road_dict)
    r_id = road_dict.get("road_id", "")
    meta = get_road_metadata(r_id, profile)
    enriched["road_name"] = meta["road_name"]
    enriched["road_type"] = meta["road_type"]
    enriched["intersection_name"] = meta["intersection_name"]
    return enriched

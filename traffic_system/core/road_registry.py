"""
traffic_system/core/road_registry.py - Canonical Urban Road & Intersection Registry
Provides ground-truth road names, intersection cross-streets, and corridor types
for all 24 urban corridors across the 8 Bangalore metropolitan zones.
"""

import re
from typing import Dict, Any, Optional

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

# High-Precision Multi-Lane Geometry & Place Recognition Taxonomy
CORRIDOR_GEO_REGISTRY: Dict[str, Dict[str, Any]] = {
    "RD_BLR_01": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Curbside / Commercial Access", "Lane 2: Express Through Arterial"],
        "speed_limit_kmh": 50.0,
        "coordinates": [[12.9720, 77.6400], [12.9784, 77.6408], [12.9850, 77.6415]],
        "place_aliases": ["100 feet road", "indiranagar 100 ft", "cmh road junction", "hal 2nd stage", "12th main indiranagar", "indiranagar metro"]
    },
    "RD_BLR_02": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Transit / Bus Stop", "Lane 2: CBD Core Through", "Lane 3: Right Turn to Cubbon Park"],
        "speed_limit_kmh": 45.0,
        "coordinates": [[12.9730, 77.6040], [12.9756, 77.6066], [12.9770, 77.6090]],
        "place_aliases": ["anil kumble circle", "mg road", "m.g. road", "chinnaswamy stadium", "cubbon road", "commercial street"]
    },
    "RD_BLR_03": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Service Road Merge", "Lane 2: Airport Express", "Lane 3: Fast Transit"],
        "speed_limit_kmh": 80.0,
        "coordinates": [[13.0200, 77.5920], [13.0358, 77.5970], [13.0500, 77.6020]],
        "place_aliases": ["ballari road", "bellary road", "airport road", "kempegowda airport express", "nh-44 hebbal", "sahakara nagar"]
    },
    "RD_BLR_04": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Metro Station Access", "Lane 2: CMH Metro Express"],
        "speed_limit_kmh": 45.0,
        "coordinates": [[12.9780, 77.6360], [12.9790, 77.6420], [12.9800, 77.6480]],
        "place_aliases": ["cmh road", "chinmaya mission hospital road", "indiranagar metro station", "cmh hospital", "swami vivekananda road"]
    },
    "RD_BLR_05": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Outer Ring Road Ramp", "Lane 2: Flyover Main Span", "Lane 3: High-Speed Elevated Spurt"],
        "speed_limit_kmh": 65.0,
        "coordinates": [[13.0320, 77.5950], [13.0380, 77.5985], [13.0440, 77.6010]],
        "place_aliases": ["hebbal flyover", "hebbal interchange", "hebbal lake", "manyata junction", "outer ring road hebbal"]
    },
    "RD_BLR_06": {
        "lanes": 8,
        "lane_breakdown": ["Lane 1: Toll Gate Merge", "Lane 2: Surface Corridor", "Lane 3: Elevated Expressway 1", "Lane 4: Elevated Expressway 2"],
        "speed_limit_kmh": 80.0,
        "coordinates": [[12.8350, 77.6550], [12.8452, 77.6602], [12.8600, 77.6650]],
        "place_aliases": ["hosur road", "elevated expressway", "electronic city elevated", "electronic city expressway", "bommanahalli", "attibele highway", "e-city toll", "electronic city flyover"]
    },
    "RD_BLR_07": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Tech Park Shuttle Lane", "Lane 2: ITPL Main Through"],
        "speed_limit_kmh": 50.0,
        "coordinates": [[12.9800, 77.7200], [12.9850, 77.7280], [12.9900, 77.7360]],
        "place_aliases": ["itpl main road", "itpl", "international tech park", "whitefield main road", "hope farm junction", "kadugodi metro"]
    },
    "RD_BLR_08": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Shopping Complex Parking Merge", "Lane 2: Jayanagar Commercial Spine"],
        "speed_limit_kmh": 40.0,
        "coordinates": [[12.9220, 77.5900], [12.9250, 77.5938], [12.9280, 77.5980]],
        "place_aliases": ["jayanagar 4th block", "jayanagar complex", "4th block bus terminus", "jayanagar bda complex", "3rd block jayanagar"]
    },
    "RD_BLR_09": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Marathahalli Market Ramp", "Lane 2: Ring Road Overpass Through", "Lane 3: East Expressway"],
        "speed_limit_kmh": 60.0,
        "coordinates": [[12.9510, 77.6950], [12.9560, 77.7010], [12.9620, 77.7080]],
        "place_aliases": ["marathahalli bridge", "marathahalli interchange", "outer ring road marathahalli", "innovative multiplex", "kalamandir junction"]
    },
    "RD_BLR_10": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Curbside Retail Deceleration", "Lane 2: Sarjapur Arterial Through"],
        "speed_limit_kmh": 50.0,
        "coordinates": [[12.9200, 77.6450], [12.9240, 77.6520], [12.9290, 77.6600]],
        "place_aliases": ["sarjapur road", "sarjapur main road", "wipro sarjapur", "carmelaram", "bellandur sarjapur junction"]
    },
    "RD_BLR_11": {
        "lanes": 8,
        "lane_breakdown": ["Lane 1: BTM Ramp", "Lane 2: Hosur Merge", "Lane 3: Elevated Flyover Spurt", "Lane 4: Bus Priority Slip"],
        "speed_limit_kmh": 50.0,
        "coordinates": [[12.9120, 77.6180], [12.9176, 77.6238], [12.9220, 77.6290]],
        "place_aliases": ["silk board junction", "central silk board", "silk board flyover", "btm silk board", "silk board metro interchange"]
    },
    "RD_BLR_12": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Retail Curb Friction Lane", "Lane 2: 80 Feet Throughway"],
        "speed_limit_kmh": 45.0,
        "coordinates": [[12.9320, 77.6210], [12.9352, 77.6245], [12.9380, 77.6280]],
        "place_aliases": ["sony world junction", "sony world crossing", "koramangala 4th block", "koramangala 5th block", "jyoti nivas college link"]
    },
    "RD_BLR_13": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Lalbagh West Entry", "Lane 2: Rotary Flow Lane 1", "Lane 3: Rotary Flow Lane 2"],
        "speed_limit_kmh": 45.0,
        "coordinates": [[12.9250, 77.5750], [12.9280, 77.5790], [12.9320, 77.5830]],
        "place_aliases": ["south end circle", "south end rotary", "lalbagh west gate", "south end metro", "basavanagudi link"]
    },
    "RD_BLR_14": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Halasuru Entry Slip", "Lane 2: Trinity Metro Through", "Lane 3: MG Road CBD Flyway"],
        "speed_limit_kmh": 50.0,
        "coordinates": [[12.9690, 77.6150], [12.9725, 77.6200], [12.9760, 77.6250]],
        "place_aliases": ["trinity circle", "trinity metro station", "taj mg road", "halasuru lake road", "victoria road"]
    },
    "RD_BLR_15": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Freight / Heavy Vehicle Lane", "Lane 2: Highway Express Through", "Lane 3: Express Overtaking"],
        "speed_limit_kmh": 70.0,
        "coordinates": [[13.0200, 77.5320], [13.0280, 77.5400], [13.0350, 77.5480]],
        "place_aliases": ["tumkur road", "nh-48 freight expressway", "peenya industrial corridor", "goraguntepalya", "dasarahalli metro"]
    },
    "RD_BLR_16": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Railway Station Slip Lane", "Lane 2: Circle Circulatory Flow", "Lane 3: Malleshwaram Flyover"],
        "speed_limit_kmh": 50.0,
        "coordinates": [[13.0200, 77.5480], [13.0238, 77.5529], [13.0280, 77.5580]],
        "place_aliases": ["yeshwanthpur circle", "yeshwanthpur railway station", "yeshwanthpur market", "iisc gate link", "orion mall road"]
    },
    "RD_BLR_17": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Domlur Flyover Slip", "Lane 2: Old Airport Arterial Through"],
        "speed_limit_kmh": 50.0,
        "coordinates": [[12.9550, 77.6420], [12.9600, 77.6480], [12.9660, 77.6540]],
        "place_aliases": ["old airport road", "hal airport road", "domlur flyover", "command hospital", "manipal hospital road", "murugeshpalya"]
    },
    "RD_BLR_18": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Pedestrian Promenade Merge", "Lane 2: Commercial Spine Corridor"],
        "speed_limit_kmh": 40.0,
        "coordinates": [[12.9700, 77.6060], [12.9730, 77.6075], [12.9760, 77.6090]],
        "place_aliases": ["brigade road", "residency road junction", "garuda mall", "richmond town", "opera house crossing", "mg road brigade link"]
    },
    "RD_BLR_19": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Residential Connector Lane", "Lane 2: North Express Through"],
        "speed_limit_kmh": 60.0,
        "coordinates": [[13.0450, 77.6250], [13.0550, 77.6320], [13.0650, 77.6390]],
        "place_aliases": ["thanisandra main road", "bhartiya city", "manyata back gate", "nagavara link", "hegde nagar"]
    },
    "RD_BLR_20": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Campus Shuttle Drop-off", "Lane 2: Tech Spine Through", "Lane 3: Phase 1 Expressway Loop"],
        "speed_limit_kmh": 60.0,
        "coordinates": [[12.8340, 77.6710], [12.8399, 77.6770], [12.8460, 77.6830]],
        "place_aliases": ["electronic city phase 1", "electronic city expressway", "electronic city", "e-city expressway", "infosys campus", "wipro gate e-city", "velankani tech park", "e-city phase 1 toll"]
    },
    "RD_BLR_21": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Lake Perimeter Bypass", "Lane 2: Varthur Main Arterial"],
        "speed_limit_kmh": 50.0,
        "coordinates": [[12.9360, 77.7400], [12.9420, 77.7470], [12.9480, 77.7550]],
        "place_aliases": ["varthur road", "kundalahalli gate", "varthur lake road", "whitefield south perimeter", "marathahalli-varthur road"]
    },
    "RD_BLR_22": {
        "lanes": 6,
        "lane_breakdown": ["Lane 1: Metro Line 4 Ground Track", "Lane 2: Kanakapura Main Highway", "Lane 3: South Transit Express"],
        "speed_limit_kmh": 60.0,
        "coordinates": [[12.8980, 77.5700], [12.9050, 77.5750], [12.9120, 77.5800]],
        "place_aliases": ["kanakapura road", "sarakki signal", "banashankari metro link", "art of living road", "konanakunte cross"]
    },
    "RD_BLR_23": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: NGV Commercial Slip", "Lane 2: 80 Feet Transit Spine"],
        "speed_limit_kmh": 45.0,
        "coordinates": [[12.9350, 77.6140], [12.9400, 77.6200], [12.9450, 77.6260]],
        "place_aliases": ["koramangala 80 feet road", "national games village", "ngv gate", "passport seva kendra koramangala", "regional passport office"]
    },
    "RD_BLR_24": {
        "lanes": 4,
        "lane_breakdown": ["Lane 1: Market Pedestrian Friction Track", "Lane 2: Margosa Transit Flow"],
        "speed_limit_kmh": 40.0,
        "coordinates": [[12.9980, 77.5660], [13.0030, 77.5700], [13.0080, 77.5740]],
        "place_aliases": ["malleshwaram 8th cross", "margosa road", "sampige road", "malleshwaram market", "kaadu malleswara temple", "18th cross malleshwaram"]
    },
}

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
            geo = CORRIDOR_GEO_REGISTRY.get(r_id, {})
            lanes = geo.get("lanes", 4)
            ff_spd = geo.get("speed_limit_kmh", 50.0)
            defn = CorridorDefinition(
                road_id=r_id,
                bangalore_name=info.get("bangalore_name", r_id),
                global_name=info.get("global_name", r_id),
                city_zone=info.get("city_zone", "Indiranagar"),
                road_type=info.get("road_type", "Primary Arterial"),
                intersection_id=info.get("intersection_id", f"INT_{r_id}"),
                intersection_name=info.get("intersection_name", f"INT_{r_id}"),
                free_flow_speed=ff_spd,
                design_capacity=lanes * 14000
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

def get_corridor_lane_info(road_id: str) -> Dict[str, Any]:
    """Returns lane configuration and breakdown for a given corridor."""
    geo = CORRIDOR_GEO_REGISTRY.get(road_id, {})
    return {
        "road_id": road_id,
        "lanes": geo.get("lanes", 4),
        "lane_breakdown": geo.get("lane_breakdown", ["Lane 1: Through", "Lane 2: Through"]),
        "speed_limit_kmh": geo.get("speed_limit_kmh", 50.0),
        "coordinates": geo.get("coordinates", [])
    }

def get_corridor_coordinates(road_id: str) -> List[List[float]]:
    """Returns GPS polyline coordinates [[lat, lon], ...] for a corridor."""
    geo = CORRIDOR_GEO_REGISTRY.get(road_id, {})
    return geo.get("coordinates", [])

def match_places_to_corridors(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fuzzy place recognition searching Bengaluru landmarks, corridors, metro stations, and highway junctions.
    Returns matched corridors with coordinates, zone, and canonical road_id.
    """
    if not query or not query.strip():
        # Default top key transit hubs in Bengaluru
        default_ids = ["RD_BLR_02", "RD_BLR_11", "RD_BLR_05", "RD_BLR_01", "RD_BLR_07"]
        return [
            {
                "road_id": r_id,
                "name": get_road_name(r_id),
                "city_zone": ROAD_REGISTRY[r_id]["city_zone"],
                "road_type": ROAD_REGISTRY[r_id]["road_type"],
                "intersection_name": ROAD_REGISTRY[r_id]["intersection_name"],
                "coordinates": get_corridor_coordinates(r_id),
                "lanes": CORRIDOR_GEO_REGISTRY.get(r_id, {}).get("lanes", 4),
                "match_type": "landmark_hub"
            }
            for r_id in default_ids if r_id in ROAD_REGISTRY
        ]

    q_clean = query.strip().lower()
    matches = []
    q_tokens = [t for t in re.split(r"[\s\-_,.]+", q_clean) if len(t) >= 3]

    for r_id, info in ROAD_REGISTRY.items():
        geo = CORRIDOR_GEO_REGISTRY.get(r_id, {})
        aliases = [str(a).lower() for a in geo.get("place_aliases", [])]
        bangalore_name = str(info.get("bangalore_name", "")).lower()
        global_name = str(info.get("global_name", "")).lower()
        zone = str(info.get("city_zone", "")).lower()
        int_name = str(info.get("intersection_name", "")).lower()

        all_search_strings = [bangalore_name, global_name, zone, int_name] + aliases

        score = 0
        if q_clean == r_id.lower():
            score = 100
        elif any(q_clean == a or q_clean == bangalore_name for a in aliases):
            score = 95
        elif any(q_clean in a or a in q_clean for a in aliases if len(a) >= 4):
            score = 85
        elif q_clean in bangalore_name or bangalore_name in q_clean or q_clean in global_name:
            score = 80
        elif any(q_clean in s or s in q_clean for s in [int_name, zone] if len(s) >= 4):
            score = 65
        else:
            # Token overlap score
            matched_tokens = sum(
                1 for tok in q_tokens
                if any(tok in candidate for candidate in all_search_strings)
            )
            if q_tokens and matched_tokens >= min(2, len(q_tokens)):
                score = 50 + (matched_tokens * 10)

        if score > 0:
            matches.append({
                "score": score,
                "road_id": r_id,
                "name": info.get("bangalore_name", r_id),
                "city_zone": info.get("city_zone", ""),
                "road_type": info.get("road_type", ""),
                "intersection_name": info.get("intersection_name", ""),
                "coordinates": geo.get("coordinates", []),
                "lanes": geo.get("lanes", 4),
                "lane_breakdown": geo.get("lane_breakdown", []),
                "match_type": "exact" if score >= 80 else "alias"
            })

    matches.sort(key=lambda m: -m["score"])
    return matches[:limit]

def enrich_road_info(road_dict: Dict[str, Any], profile: str = "global") -> Dict[str, Any]:
    """Enriches a road dictionary with canonical road name, intersection details, and lane geometry."""
    enriched = dict(road_dict)
    r_id = road_dict.get("road_id", "")
    meta = get_road_metadata(r_id, profile)
    lane_info = get_corridor_lane_info(r_id)
    enriched["road_name"] = meta["road_name"]
    enriched["road_type"] = meta["road_type"]
    enriched["intersection_name"] = meta["intersection_name"]
    enriched["lanes"] = lane_info["lanes"]
    enriched["lane_breakdown"] = lane_info["lane_breakdown"]
    enriched["speed_limit_kmh"] = lane_info["speed_limit_kmh"]
    enriched["coordinates"] = lane_info["coordinates"]
    return enriched


# Empirical calibrated free-flow speeds for Bengaluru corridors
_CORRIDOR_FREE_FLOW_SPEEDS: Dict[str, float] = {
    "RD_BLR_01": 48.0, "RD_BLR_02": 45.0, "RD_BLR_03": 60.0, "RD_BLR_04": 46.0,
    "RD_BLR_05": 55.0, "RD_BLR_06": 65.0, "RD_BLR_07": 50.0, "RD_BLR_08": 44.0,
    "RD_BLR_09": 52.0, "RD_BLR_10": 48.0, "RD_BLR_11": 42.0, "RD_BLR_12": 45.0,
    "RD_BLR_13": 46.0, "RD_BLR_14": 48.0, "RD_BLR_15": 58.0, "RD_BLR_16": 50.0,
    "RD_BLR_17": 50.0, "RD_BLR_18": 42.0, "RD_BLR_19": 52.0, "RD_BLR_20": 60.0,
    "RD_BLR_21": 48.0, "RD_BLR_22": 52.0, "RD_BLR_23": 46.0, "RD_BLR_24": 44.0,
}


def normalize_corridor_id(corridor_id: str, to_code: bool = False) -> str:
    """
    Normalizes corridor identifiers supporting bidirectional mapping between
    'BLR-COR-XX' and 'RD_BLR_XX' (case-insensitive, trimming whitespace).

    E.g.
    normalize_corridor_id('BLR-COR-01') -> 'RD_BLR_01'
    normalize_corridor_id('RD_BLR_01')  -> 'RD_BLR_01'
    normalize_corridor_id('blr-cor-01') -> 'RD_BLR_01'
    normalize_corridor_id('RD_BLR_01', to_code=True) -> 'BLR-COR-01'
    """
    if not corridor_id or not isinstance(corridor_id, str):
        return ""
    clean = corridor_id.strip().upper()

    # Match BLR-COR-XX, BLR_COR_XX, BLRCORXX
    m_blr = re.match(r"^BLR[-_]?COR[-_]?(\d+)$", clean)
    if m_blr:
        num = int(m_blr.group(1))
        return f"BLR-COR-{num:02d}" if to_code else f"RD_BLR_{num:02d}"

    # Match RD_BLR_XX, RD-BLR-XX, RDBLRXX
    m_rd = re.match(r"^RD[-_]?BLR[-_]?(\d+)$", clean)
    if m_rd:
        num = int(m_rd.group(1))
        return f"BLR-COR-{num:02d}" if to_code else f"RD_BLR_{num:02d}"

    return clean


def corridor_id_to_code(corridor_id: str) -> str:
    """Converts RD_BLR_XX or BLR-COR-XX to standard code BLR-COR-XX."""
    return normalize_corridor_id(corridor_id, to_code=True)


def corridor_code_to_id(corridor_code: str) -> str:
    """Converts BLR-COR-XX or RD_BLR_XX to canonical road ID RD_BLR_XX."""
    return normalize_corridor_id(corridor_code, to_code=False)


def compute_mfd_density(
    flow_q: float,
    speed_v: float,
    max_density: float = 150.0,
    min_speed: float = 5.0
) -> float:
    """
    Computes Macroscopic Fundamental Diagram (MFD) density k = q / v
    with robust numerical safeguards (minimum speed clamp, physical jam ceiling).

    - Speed is clamped to v >= min_speed (default 5.0 km/h) to prevent division by zero.
    - Density is capped at max_density (default 150.0 veh/km) to respect physical capacity.
    - Non-negative clamping ensures flow and speed do not produce negative densities.
    """
    v_safe = max(float(min_speed), float(speed_v))
    q_safe = max(0.0, float(flow_q))
    k = q_safe / v_safe
    return round(min(float(max_density), max(0.0, k)), 2)


def get_corridor(corridor_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves enriched corridor details by ID or code.
    Supports both 'RD_BLR_XX' and 'BLR-COR-XX' (case-insensitive, trimmed).

    Returns dictionary with:
    - corridor_id: canonical ID (e.g. 'RD_BLR_01')
    - corridor_code / code: standard code (e.g. 'BLR-COR-01')
    - name / corridor_name: human-readable name
    - zone / city_zone: Bengaluru municipal zone
    - road_type: arterial road classification
    - lanes: integer lane count (4, 6, 8)
    - speed_limit_kmh: posted speed limit
    - free_flow_speed: calibrated free flow speed
    - coordinates: GPS polyline coordinates [[lat, lng], ...]
    - path: list of [{'lat': lat, 'lng': lng}, ...]
    - junctions: list of junction status objects
    """
    norm_id = normalize_corridor_id(corridor_id)
    if not norm_id or norm_id not in ROAD_REGISTRY:
        return None

    info = ROAD_REGISTRY[norm_id]
    geo = CORRIDOR_GEO_REGISTRY.get(norm_id, {})
    m = re.match(r"^RD_BLR_(\d+)$", norm_id)
    code = f"BLR-COR-{int(m.group(1)):02d}" if m else norm_id

    coords = geo.get("coordinates", [])
    path = [{"lat": pt[0], "lng": pt[1]} for pt in coords]

    speed_limit = float(geo.get("speed_limit_kmh", 50.0))
    ff_speed = float(_CORRIDOR_FREE_FLOW_SPEEDS.get(norm_id, speed_limit))

    int_id = info.get("intersection_id", f"INT_{norm_id.replace('RD_', '')}")
    int_name = info.get("intersection_name", f"{info.get('bangalore_name', norm_id)} Crossing")

    junctions = []
    if coords:
        mid_idx = len(coords) // 2
        junctions.append({
            "junction_id": int_id,
            "intersection_id": int_id,
            "junction_name": int_name,
            "intersection_name": int_name,
            "lat": coords[mid_idx][0],
            "lng": coords[mid_idx][1],
            "control_type": "Actuated Signal",
            "signal_status": "Operational",
            "level_of_service": "Moderate",
            "queue_meters": 35.0,
            "control_delay_sec": 24.5
        })
    else:
        junctions.append({
            "junction_id": int_id,
            "intersection_id": int_id,
            "junction_name": int_name,
            "intersection_name": int_name,
            "lat": 12.9716,
            "lng": 77.5946,
            "control_type": "Actuated Signal",
            "signal_status": "Operational",
            "level_of_service": "Moderate",
            "queue_meters": 35.0,
            "control_delay_sec": 24.5
        })

    return {
        "corridor_id": norm_id,
        "road_id": norm_id,
        "corridor_code": code,
        "code": code,
        "name": info.get("bangalore_name", norm_id),
        "corridor_name": info.get("bangalore_name", norm_id),
        "bangalore_name": info.get("bangalore_name", norm_id),
        "global_name": info.get("global_name", norm_id),
        "zone": info.get("city_zone", "Indiranagar"),
        "city_zone": info.get("city_zone", "Indiranagar"),
        "road_type": info.get("road_type", "Primary Arterial"),
        "lanes": int(geo.get("lanes", 4)),
        "lane_breakdown": geo.get("lane_breakdown", []),
        "speed_limit": speed_limit,
        "speed_limit_kmh": speed_limit,
        "free_flow_speed": ff_speed,
        "free_flow_speed_kmh": ff_speed,
        "coordinates": coords,
        "path": path,
        "intersection_id": int_id,
        "intersection_name": int_name,
        "junctions": junctions,
        "place_aliases": geo.get("place_aliases", [])
    }


def get_all_corridors() -> List[Dict[str, Any]]:
    """Returns list of all 24 Bengaluru metropolitan corridors enriched with geometry and metadata."""
    corridors = []
    for r_id in ROAD_REGISTRY:
        cor = get_corridor(r_id)
        if cor:
            corridors.append(cor)
    return corridors


def get_road(road_id: str) -> Optional[Dict[str, Any]]:
    """Alias for get_corridor."""
    return get_corridor(road_id)


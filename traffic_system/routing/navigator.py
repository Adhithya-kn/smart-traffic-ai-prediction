

import heapq
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime
from traffic_system.core.entities import (
    RouteEvaluation, CongestionLevel, CONGESTION_RANKS, RANK_TO_CONGESTION,
    congestion_rank, rank_to_congestion, make_feature_vector
)
from traffic_system.core.road_registry import enrich_road_info, get_road_name
from traffic_system.core.time_utils import parse_time_parts
from traffic_system.core.traffic_physics import classify_speed_los, calculate_capacity_utilization
from traffic_system.events.event_manager import EventManager
from traffic_system.models.predictor import TrafficPredictor

CONGESTION_SEVERITY_ORDER = CONGESTION_RANKS
ORDER_TO_CONGESTION = RANK_TO_CONGESTION

# Empirical Hourly Inflow & Velocity Factors calibrated to standard urban diurnal flow curves
EMPIRICAL_HOURLY_FACTORS = {
    0:  {"vol": 0.22, "spd": 1.30, "cong": "Low"},
    1:  {"vol": 0.20, "spd": 1.30, "cong": "Low"},
    2:  {"vol": 0.20, "spd": 1.30, "cong": "Low"},
    3:  {"vol": 0.20, "spd": 1.30, "cong": "Low"},
    4:  {"vol": 0.25, "spd": 1.28, "cong": "Low"},
    5:  {"vol": 0.35, "spd": 1.25, "cong": "Low"},
    6:  {"vol": 0.55, "spd": 1.15, "cong": "Low"},
    7:  {"vol": 0.80, "spd": 1.05, "cong": "Moderate"},
    8:  {"vol": 1.20, "spd": 0.80, "cong": "High"},
    9:  {"vol": 1.35, "spd": 0.70, "cong": "Severe"},     # Morning Inflow Commute Peak
    10: {"vol": 1.10, "spd": 0.85, "cong": "Moderate"},
    11: {"vol": 0.90, "spd": 0.95, "cong": "Moderate"},   # Midday Arterial Flow
    12: {"vol": 0.95, "spd": 0.92, "cong": "Moderate"},
    13: {"vol": 0.88, "spd": 0.96, "cong": "Moderate"},
    14: {"vol": 0.92, "spd": 0.94, "cong": "Moderate"},
    15: {"vol": 1.05, "spd": 0.88, "cong": "Moderate"},
    16: {"vol": 1.22, "spd": 0.78, "cong": "High"},
    17: {"vol": 1.38, "spd": 0.68, "cong": "Severe"},     # Evening Commute Peak
    18: {"vol": 1.35, "spd": 0.70, "cong": "Severe"},
    19: {"vol": 1.15, "spd": 0.82, "cong": "High"},
    20: {"vol": 0.85, "spd": 1.00, "cong": "Moderate"},   # Evening Redistribution
    21: {"vol": 0.65, "spd": 1.10, "cong": "Moderate"},
    22: {"vol": 0.45, "spd": 1.20, "cong": "Low"},        # Night Dissipation
    23: {"vol": 0.30, "spd": 1.25, "cong": "Low"},
}

# Calibrated Physical Corridor Lengths in kilometers (Bangalore Arterial Survey)
CALIBRATED_ROAD_LENGTHS_KM = {
    "RD_BLR_01": 2.4,  # 100 Feet Road (Indiranagar)
    "RD_BLR_02": 1.8,  # Anil Kumble Circle (MG Road CBD)
    "RD_BLR_03": 4.5,  # Ballari Road (Hebbal / NH-44)
    "RD_BLR_04": 2.2,  # CMH Road (Indiranagar)
    "RD_BLR_05": 2.8,  # Hebbal Flyover Interchange
    "RD_BLR_06": 5.2,  # Hosur Road Elevated Expressway
    "RD_BLR_07": 3.8,  # ITPL Main Road (Whitefield)
    "RD_BLR_08": 2.1,  # Jayanagar 4th Block
    "RD_BLR_09": 3.2,  # Marathahalli Bridge
    "RD_BLR_10": 3.6,  # Sarjapur Road
    "RD_BLR_11": 3.0,  # Silk Board Junction
    "RD_BLR_12": 2.2,  # Sony World Junction
    "RD_BLR_13": 2.0,  # South End Circle
    "RD_BLR_14": 2.1,  # Trinity Circle (MG Road CBD)
    "RD_BLR_15": 4.8,  # Tumkur Road (Yeshwanthpur NH-4)
    "RD_BLR_16": 2.3,  # Yeshwanthpur Circle
    "RD_BLR_17": 3.5,  # Old Airport Road (Indiranagar)
    "RD_BLR_18": 1.5,  # Brigade Road (MG Road CBD)
    "RD_BLR_19": 4.0,  # Thanisandra Main Road (Hebbal North)
    "RD_BLR_20": 3.2,  # Electronic City Phase 1 (Electronic City South)
    "RD_BLR_21": 4.2,  # Varthur Road (Whitefield)
    "RD_BLR_22": 3.8,  # Kanakapura Road (Jayanagar)
    "RD_BLR_23": 2.4,  # Koramangala 80 Feet Road (Koramangala)
    "RD_BLR_24": 1.9,  # Malleshwaram 8th Cross (Yeshwanthpur West)
}

# Ground-Truth Inter-Zone Arterial Bridges connecting Bangalore's 8 metropolitan zones
INTER_ZONE_BRIDGES = [
    # Indiranagar <-> MG Road CBD
    ("RD_BLR_01", "RD_BLR_14", 2.2),  # 100ft Rd <-> Trinity Circle
    ("RD_BLR_04", "RD_BLR_14", 2.0),  # CMH Rd <-> Trinity Circle (Ulsoor link)
    ("RD_BLR_17", "RD_BLR_18", 2.5),  # Old Airport Rd <-> Brigade Rd
    # Indiranagar <-> Koramangala
    ("RD_BLR_01", "RD_BLR_12", 2.6),  # 100ft Rd <-> Sony World (Domlur Intermediate Ring Rd)
    ("RD_BLR_04", "RD_BLR_12", 2.8),  # CMH Rd <-> Sony World
    ("RD_BLR_17", "RD_BLR_23", 2.2),  # Old Airport Rd <-> 80ft Rd
    # Indiranagar <-> Whitefield
    ("RD_BLR_01", "RD_BLR_07", 5.5),  # 100ft Rd <-> ITPL Main Rd (Old Madras Rd)
    ("RD_BLR_04", "RD_BLR_09", 5.0),  # CMH Rd <-> Marathahalli (HAL Old Airport Rd)
    ("RD_BLR_17", "RD_BLR_09", 3.8),  # Old Airport Rd <-> Marathahalli
    # Whitefield <-> Koramangala
    ("RD_BLR_09", "RD_BLR_10", 4.2),  # Marathahalli <-> Sarjapur Rd (Outer Ring Rd)
    ("RD_BLR_21", "RD_BLR_10", 3.8),  # Varthur Rd <-> Sarjapur Rd
    # MG Road CBD <-> Jayanagar
    ("RD_BLR_02", "RD_BLR_13", 3.2),  # Anil Kumble <-> South End Circle (Lalbagh Fort Rd)
    ("RD_BLR_18", "RD_BLR_08", 3.6),  # Brigade Rd <-> Jayanagar 4th Block
    # Koramangala <-> Electronic City South
    ("RD_BLR_10", "RD_BLR_11", 2.4),  # Sarjapur Rd <-> Silk Board
    ("RD_BLR_12", "RD_BLR_11", 2.5),  # Sony World <-> Silk Board (Koramangala 100ft Rd)
    ("RD_BLR_23", "RD_BLR_20", 4.2),  # 80ft Rd <-> Electronic City Phase 1
    # Electronic City South <-> Jayanagar
    ("RD_BLR_06", "RD_BLR_13", 4.0),  # Hosur Rd <-> South End Circle
    ("RD_BLR_11", "RD_BLR_13", 3.5),  # Silk Board <-> South End Circle (BTM Layout)
    ("RD_BLR_20", "RD_BLR_22", 4.5),  # EC Phase 1 <-> Kanakapura Rd
    # Hebbal North <-> MG Road CBD
    ("RD_BLR_05", "RD_BLR_14", 4.8),  # Hebbal Flyover <-> Trinity Circle
    ("RD_BLR_05", "RD_BLR_02", 4.5),  # Hebbal Flyover <-> Anil Kumble Circle (Palace Cross)
    # Hebbal North <-> Yeshwanthpur West
    ("RD_BLR_03", "RD_BLR_16", 3.4),  # Ballari Rd <-> Yeshwanthpur Circle (Outer Ring Rd)
    ("RD_BLR_19", "RD_BLR_24", 4.2),  # Thanisandra Rd <-> Malleshwaram 8th Cross
    # Yeshwanthpur West <-> Jayanagar
    ("RD_BLR_15", "RD_BLR_08", 5.8),  # Tumkur Rd <-> Jayanagar 4th Block (Chord Rd)
    # Yeshwanthpur West <-> MG Road CBD
    ("RD_BLR_16", "RD_BLR_02", 4.2),  # Yeshwanthpur Circle <-> Anil Kumble Circle (Raj Bhavan)
    ("RD_BLR_24", "RD_BLR_02", 3.5),  # Malleshwaram 8th Cross <-> Anil Kumble Circle
]

class UrbanTopologyGraph:
    """Directed weighted graph of the 16 Bangalore corridors with traversal travel times in minutes."""
    def __init__(self, topology: Dict[str, dict]):
        self.topology = topology
        self.adj: Dict[str, List[Tuple[str, float]]] = {r: [] for r in topology}
        self.road_lengths: Dict[str, float] = {}
        self._build_network_graph()

    def _build_network_graph(self):
        # 1. Assign calibrated physical road lengths (km)
        for r_id in self.topology:
            self.road_lengths[r_id] = CALIBRATED_ROAD_LENGTHS_KM.get(r_id, 2.5)

        # 2. Connect corridors within each zone (e.g. 100ft Rd <-> CMH Rd in Indiranagar)
        zone_map: Dict[str, List[str]] = {}
        for r_id, info in self.topology.items():
            z = info["city_zone"]
            zone_map.setdefault(z, []).append(r_id)

        for z_name, roads in zone_map.items():
            if len(roads) >= 2:
                u, v = roads[0], roads[1]
                len_uv = round((self.road_lengths[u] + self.road_lengths[v]) / 2.0, 2)
                self.adj[u].append((v, len_uv))
                self.adj[v].append((u, len_uv))

        # 3. Connect real-world inter-zone arterial bridges (bidirectional)
        for r1, r2, bridge_len in INTER_ZONE_BRIDGES:
            if r1 in self.adj and r2 in self.adj:
                if not any(nbr == r2 for nbr, _ in self.adj[r1]):
                    self.adj[r1].append((r2, bridge_len))
                if not any(nbr == r1 for nbr, _ in self.adj[r2]):
                    self.adj[r2].append((r1, bridge_len))

    def dijkstra_shortest_path(self, origin: str, destination: str,
                               link_travel_times: Dict[Tuple[str, str], float]) -> Tuple[List[str], float]:
        """Calculates optimal path minimizing physical traversal time (minutes)."""
        if origin not in self.adj or destination not in self.adj:
            return [origin, destination], 0.0
        if origin == destination:
            return [origin], 0.0

        dist = {node: float("inf") for node in self.adj}
        prev = {node: None for node in self.adj}
        dist[origin] = 0.0
        pq: List[Tuple[float, str]] = [(0.0, origin)]

        while pq:
            current_dist, u = heapq.heappop(pq)
            if u == destination:
                break
            if current_dist > dist[u]:
                continue

            for v, base_len in self.adj.get(u, []):
                # Cost is traversal travel time in minutes
                t_travel = link_travel_times.get((u, v), (base_len / 35.0) * 60.0)
                new_dist = current_dist + t_travel

                if new_dist < dist[v]:
                    dist[v] = new_dist
                    prev[v] = u
                    heapq.heappush(pq, (new_dist, v))

        # Reconstruct path
        path = []
        curr: Optional[str] = destination
        while curr:
            path.append(curr)
            curr = prev.get(curr)
        path.reverse()

        if len(path) >= 2 and path[0] == origin:
            return path, round(dist[destination], 1)
        return [origin, destination], 0.0


class RouteNavigator:
    """Evaluates routes, predicts forward-horizon bottlenecks, and calculates event-aware bypass routes."""
    def __init__(self, predictor: TrafficPredictor, event_manager: EventManager):
        self.predictor = predictor
        self.event_manager = event_manager
        if not self.predictor.topology:
            self.predictor.load_artifacts()
        self.graph = UrbanTopologyGraph(self.predictor.topology)

    def get_available_roads(self, zone: Optional[str] = None, profile: str = "global") -> List[Dict[str, Any]]:
        """Returns list of road segments enriched with road names."""
        roads = []
        for r_id, info in sorted(self.predictor.topology.items()):
            if zone and info["city_zone"].lower() != zone.lower():
                continue
            enriched = enrich_road_info(info, profile=profile)
            roads.append(enriched)
        return roads

    def _build_route_features(self, route: List[str], speeds: Dict[str, float], vols: Dict[str, int], hour: int, dow: int, weekend: int, cong: str) -> List[Dict[str, Any]]:
        return [
            make_feature_vector(
                road_id=r, intersection_id=self.predictor.topology[r]["intersection_id"],
                city_zone=self.predictor.topology[r]["city_zone"], vehicle_count=vols[r],
                average_speed=speeds[r],
                capacity_utilization=round((vols[r] / max(self.predictor.topology[r].get("capacity", 35000), 1)) * 100, 1),
                congestion_level=cong if not weekend else "Low",
                hour=hour, day_of_week=dow, is_weekend=weekend
            )
            for r in route
        ]

    def evaluate_route(self, origin_road: str, destination_road: str,
                       date_str: str, time_str: str,
                       published_only: bool = True) -> RouteEvaluation:
        """Evaluates chosen corridor path using physics-grounded travel times and ML inference."""
        if origin_road not in self.predictor.topology:
            origin_road = list(self.predictor.topology.keys())[0]
        if destination_road not in self.predictor.topology:
            destination_road = list(self.predictor.topology.keys())[1]

        orig_info = self.predictor.topology[origin_road]
        zone = orig_info["city_zone"]

        # Parse hour, day, and weekend flag
        try:
            time_clean = time_str.strip()
            if "AM" in time_clean.upper() or "PM" in time_clean.upper():
                dt = datetime.strptime(f"{date_str} {time_clean}", "%Y-%m-%d %I:%M %p")
            else:
                dt = datetime.strptime(f"{date_str} {time_clean}", "%Y-%m-%d %H:%M")
            hour = dt.hour
            day_of_week = dt.weekday()
            is_weekend = 1 if day_of_week >= 5 else 0
        except Exception:
            hour = 17
            day_of_week = 3
            is_weekend = 0

        profile = EMPIRICAL_HOURLY_FACTORS.get(hour, {"vol": 1.0, "spd": 1.0, "cong": "Moderate"})
        vol_factor = profile["vol"] * (0.65 if is_weekend else 1.0)
        spd_factor = profile["spd"] * (1.20 if is_weekend else 1.0)
        is_off_peak = hour < 6 or hour > 21

        # 1. Compute dynamic speed, volume, and traversal duration for every link in the graph
        link_times_nominal: Dict[Tuple[str, str], float] = {}
        road_speeds: Dict[str, float] = {}
        road_volumes: Dict[str, int] = {}
        road_events: Dict[str, List[Dict[str, Any]]] = {}

        for r_id, info in self.predictor.topology.items():
            events = self.event_manager.find_active_events(road_id=r_id, date=date_str, time_str=time_str, published_only=published_only)
            road_events[r_id] = events

            base_speed = float(info["avg_speed"]) * spd_factor
            base_vol = int(info["avg_volume"] * vol_factor)

            # Event impact
            speed_penalty = max([e.get("speed_impact_pct", 0) for e in events], default=0) / 100.0
            vol_surge = sum(e.get("volume_surge_vph", 0) for e in events)

            eff_speed = max(8.0, min(80.0, base_speed * (1.0 - speed_penalty)))
            eff_vol = base_vol + vol_surge

            road_speeds[r_id] = eff_speed
            road_volumes[r_id] = eff_vol

        for u in self.graph.adj:
            for v, length_km in self.graph.adj[u]:
                spd_nominal = road_speeds[v]
                # Nominal travel time in minutes: t = (L / v) * 60
                t_nom = (length_km / max(spd_nominal, 8.0)) * 60.0
                link_times_nominal[(u, v)] = t_nom

        # 2. Find Primary Route (unpenalized shortest travel-time path)
        primary_route, primary_est_time = self.graph.dijkstra_shortest_path(
            origin_road, destination_road, link_times_nominal
        )

        # 3. Batch ML inference along primary corridor
        primary_features = self._build_route_features(primary_route, road_speeds, road_volumes, hour, day_of_week, is_weekend, profile["cong"])
        corridor_events = [e for r in primary_route for e in road_events[r]]

        primary_preds_batch = self.predictor.predict_batch(primary_features)
        primary_preds = []
        primary_delays = []
        for i, (pred_c, _) in enumerate(primary_preds_batch):
            r_id = primary_route[i]
            evts = road_events[r_id]
            if is_off_peak and not evts:
                pred_c = "Low"
            elif evts:
                boost = max(e.get("severity_boost", 1) for e in evts)
                cur_rank = CONGESTION_SEVERITY_ORDER.get(pred_c, 1)
                pred_c = ORDER_TO_CONGESTION[min(3, max(cur_rank, 1 + boost))]
            primary_preds.append(pred_c)

            # Traversal time with physical event queue delay
            length_km = self.graph.road_lengths.get(r_id, 2.5)
            spd = road_speeds[r_id]
            evt_delay = sum(e.get("severity_boost", 1) * 8.0 for e in evts) if evts else 0.0
            primary_delays.append((length_km / max(spd, 8.0)) * 60.0 + evt_delay)

        primary_total_time = sum(primary_delays)
        max_rank = max(CONGESTION_SEVERITY_ORDER.get(p, 0) for p in primary_preds)
        primary_congestion = ORDER_TO_CONGESTION[max_rank]

        # Deduplicate active events
        unique_events = {e["id"]: e for e in corridor_events}
        events_list = list(unique_events.values())

        # Entering primary corridor metrics
        primary_volume = road_volumes[origin_road]
        # Space-mean speed across primary corridor: sum(L) / sum(L/v)
        total_primary_len = sum(self.graph.road_lengths.get(r, 2.5) for r in primary_route)
        primary_speed = round((total_primary_len / (primary_total_time / 60.0)), 1) if primary_total_time > 0 else road_speeds[origin_road]

        # 4. Check if rerouting is required
        is_rerouted = False
        recommended_route = list(primary_route)
        recommended_congestion = primary_congestion
        time_saved = 0.0
        alternate_volume = primary_volume
        alternate_speed = primary_speed

        if primary_congestion in ["High", "Severe"] or len(events_list) > 0:
            # Saturated / event-affected corridors receive dynamic avoidance penalty on primary edges
            bottleneck_roads = {r for r, p in zip(primary_route, primary_preds) if p in ["High", "Severe"]}
            for e in events_list:
                bottleneck_roads.update(e.get("affected_roads", []))

            penalized_link_times = dict(link_times_nominal)
            # Add queue blockage penalty along the congested primary route edges
            for k in range(len(primary_route) - 1):
                u_node = primary_route[k]
                v_node = primary_route[k + 1]
                if u_node in bottleneck_roads or v_node in bottleneck_roads:
                    penalized_link_times[(u_node, v_node)] = penalized_link_times.get((u_node, v_node), 5.0) + 30.0
                    penalized_link_times[(v_node, u_node)] = penalized_link_times.get((v_node, u_node), 5.0) + 30.0

            bypass_route, bypass_time = self.graph.dijkstra_shortest_path(
                origin_road, destination_road, penalized_link_times
            )

            # If Dijkstra finds an alternative path
            if bypass_route != primary_route and len(bypass_route) >= 2:
                bypass_features = self._build_route_features(bypass_route, road_speeds, road_volumes, hour, day_of_week, is_weekend, profile["cong"])

                bypass_preds_batch = self.predictor.predict_batch(bypass_features)
                bypass_delays = []
                bypass_preds = []
                for j, (p_class, _) in enumerate(bypass_preds_batch):
                    r_id = bypass_route[j]
                    bypass_preds.append(p_class)
                    len_km = self.graph.road_lengths.get(r_id, 2.5)
                    spd = road_speeds[r_id]
                    bypass_delays.append((len_km / max(spd, 8.0)) * 60.0)

                bypass_total_time = sum(bypass_delays)
                saved_min = round(primary_total_time - bypass_total_time, 1)

                if saved_min > 0.5:
                    is_rerouted = True
                    recommended_route = bypass_route
                    time_saved = saved_min

                    total_byp_len = sum(self.graph.road_lengths.get(r, 2.5) for r in bypass_route)
                    alternate_speed = round(total_byp_len / (bypass_total_time / 60.0), 1) if bypass_total_time > 0 else 35.0
                    alternate_volume = road_volumes[bypass_route[0]]

                    # Physical Level of Service on dynamic bypass traversal based on kinematic space-mean speed
                    if alternate_speed >= 38.0:
                        recommended_congestion = "Low"
                    elif alternate_speed >= 27.0:
                        recommended_congestion = "Moderate"
                    elif alternate_speed >= 18.0:
                        recommended_congestion = "High"
                    else:
                        rec_rank = min(2, max(CONGESTION_SEVERITY_ORDER.get(p, 0) for p in bypass_preds))
                        recommended_congestion = ORDER_TO_CONGESTION[rec_rank]

        # 5. Synthesize Narrative
        orig_name = get_road_name(origin_road)
        dest_name = get_road_name(destination_road)
        primary_names = [get_road_name(r) for r in primary_route]
        recommended_names = [get_road_name(r) for r in recommended_route]

        if is_rerouted:
            event_desc = ", ".join(e["name"] for e in events_list) if events_list else "Arterial saturation & bottleneck delay"
            bypass_mid = recommended_route[1] if len(recommended_route) > 2 else recommended_route[-1]
            bypass_mid_name = get_road_name(bypass_mid)
            narrative = (
                f"Bottleneck Detected on Primary Route ({orig_name} → {dest_name}, {primary_congestion}): {event_desc}. "
                f"Entering volume: {primary_volume:,} veh/hr at space-mean {primary_speed} km/h (Duration: {round(primary_total_time, 1)} min). "
                f"Altered Dynamic Bypass Active via {bypass_mid_name} [{bypass_mid}] ({recommended_congestion} Congestion). "
                f"Bypass operates at {alternate_volume:,} veh/hr at {alternate_speed} km/h (Duration: {round(bypass_total_time, 1)} min). "
                f"Physical travel time saved: {time_saved} minutes."
            )
        else:
            time_saved = 0.0
            narrative = (
                f"Primary Route is Optimal ({orig_name} → {dest_name}: {primary_congestion} Congestion, "
                f"{primary_volume:,} veh/hr at space-mean {primary_speed} km/h, est. duration {round(primary_total_time, 1)} min). "
                f"No faster alternate bypass exists on the network."
            )

        return RouteEvaluation(
            origin_road=origin_road,
            destination_road=destination_road,
            date=date_str,
            time=time_str,
            city_zone=zone,
            primary_route=primary_route,
            primary_congestion=primary_congestion,
            is_rerouted=is_rerouted,
            recommended_route=recommended_route,
            recommended_congestion=recommended_congestion,
            time_saved_minutes=time_saved,
            active_events=events_list,
            recommendation_narrative=narrative,
            expected_vehicle_count=primary_volume,
            corridor_speed_kmh=primary_speed,
            alternate_vehicle_count=alternate_volume,
            alternate_speed_kmh=alternate_speed,
            origin_road_name=orig_name,
            destination_road_name=dest_name,
            primary_route_names=primary_names,
            recommended_route_names=recommended_names
        )

"""
traffic_system/live/heatmap_service.py - Multi-Channel Spatio-Temporal Heatmap Engine
Integrates:
1. Traffic Forecast Layer: XGBoost class probability diffusion across horizons (T_0, T_+15m, T_+30m, T_+60m)
2. Pedestrian Crowd Layer: Fruin Walkway Level of Service & Vulnerable Road User (VRU) Conflict Index
3. Junction Chokepoint Layer: Webster cycle length (C0), green splits, Akcelik delay, and queue spillback
"""

import datetime
from typing import Dict, Any, List, Optional, Tuple
from traffic_system.core.road_registry import (
    ROAD_REGISTRY,
    CORRIDOR_GEO_REGISTRY,
    get_road_name,
    get_corridor_coordinates,
    get_intersection_name
)
from traffic_system.live.bridge import BENGALURU_CORRIDOR_GPS
from traffic_system.core.time_utils import now_iso
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager
from traffic_system.junction.junction_service import JunctionService


# Fruin Walkway Level of Service thresholds (pedestrians per square meter)
# Source: Fruin, J.J. (1971) "Pedestrian Planning and Design"
def get_fruin_los(density_sqm: float) -> str:
    if density_sqm <= 0.35:
        return "LOS A (Free Flow)"
    elif density_sqm <= 0.65:
        return "LOS B (Normal Walking)"
    elif density_sqm <= 1.05:
        return "LOS C (Moderate Friction)"
    elif density_sqm <= 1.55:
        return "LOS D (Restricted Flow)"
    elif density_sqm <= 2.25:
        return "LOS E (Severe Crowding)"
    else:
        return "LOS F (Breakdown / Crush)"


class HeatmapService:
    """
    Computes unified, multi-channel spatio-temporal telemetry for control rooms and commuter maps.
    Enforces physically bounded densities and connects ML prediction probabilities to spatial corridors.
    """

    def __init__(
        self,
        predictor: TrafficPredictor,
        junction_service: JunctionService,
        event_manager: EventManager
    ):
        self.predictor = predictor
        self.junction_service = junction_service
        self.event_manager = event_manager
        if not self.predictor.topology:
            self.predictor.load_artifacts()

    def _interpolate_polyline(self, coords: List[List[float]], sub_divisions: int = 3) -> List[List[float]]:
        """Interpolates sub-segments between polyline vertices for smooth continuous heat surfaces."""
        if not coords or len(coords) < 2:
            return coords

        interpolated: List[List[float]] = []
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i + 1]
            interpolated.append(p1)
            for step in range(1, sub_divisions):
                ratio = step / float(sub_divisions)
                lat = p1[0] + (p2[0] - p1[0]) * ratio
                lng = p1[1] + (p2[1] - p1[1]) * ratio
                interpolated.append([round(lat, 6), round(lng, 6)])
        interpolated.append(coords[-1])
        return interpolated

    def _calculate_prediction_weight(
        self,
        current_los: str,
        prob_dist: Dict[str, float],
        horizon_minutes: int
    ) -> Tuple[float, str, Dict[str, float]]:
        """
        Calculates heat intensity weight [0.15, 1.00] and projected LOS across temporal horizons.
        Uses time-interpolated softprob vectors between T_0 (observed) and T_+60m (model forecast).
        """
        # Baseline probability representation of observed state
        los_base_probs = {
            "Low": {"Low": 0.85, "Moderate": 0.12, "High": 0.02, "Severe": 0.01},
            "Moderate": {"Low": 0.15, "Moderate": 0.70, "High": 0.12, "Severe": 0.03},
            "High": {"Low": 0.03, "Moderate": 0.17, "High": 0.65, "Severe": 0.15},
            "Severe": {"Low": 0.01, "Moderate": 0.04, "High": 0.20, "Severe": 0.75}
        }
        t0_probs = los_base_probs.get(current_los, los_base_probs["Moderate"])

        tau = max(0.0, min(1.0, horizon_minutes / 60.0))
        # Linearly interpolate probability distribution towards model forecast
        interp_probs: Dict[str, float] = {}
        for cls_name in ["Low", "Moderate", "High", "Severe"]:
            p0 = t0_probs.get(cls_name, 0.25)
            p60 = prob_dist.get(cls_name, p0)
            interp_probs[cls_name] = round((1.0 - tau) * p0 + tau * p60, 4)

        # Re-normalize
        total_p = sum(interp_probs.values()) or 1.0
        for k in interp_probs:
            interp_probs[k] = round(interp_probs[k] / total_p, 4)

        # Intensity formula: weighted combination of risk classes
        weight = (
            1.00 * interp_probs.get("Severe", 0.0) +
            0.75 * interp_probs.get("High", 0.0) +
            0.45 * interp_probs.get("Moderate", 0.0) +
            0.15 * interp_probs.get("Low", 0.0)
        )
        weight = round(max(0.15, min(1.0, weight)), 3)

        # Argmax LOS for horizon
        proj_los = max(interp_probs.items(), key=lambda x: x[1])[0]

        return weight, proj_los, interp_probs

    def _compute_traffic_layer(self, horizon_minutes: int, now_dt: datetime.datetime) -> List[Dict[str, Any]]:
        """Builds corridor road segments with physical density and spatio-temporal predictions."""
        traffic_segments: List[Dict[str, Any]] = []
        hour = now_dt.hour
        dow = now_dt.weekday()
        is_weekend = 1 if dow >= 5 else 0

        for r_id, info in ROAD_REGISTRY.items():
            geo = CORRIDOR_GEO_REGISTRY.get(r_id, {})
            coords = get_corridor_coordinates(r_id)
            if not coords or len(coords) < 2:
                gps = BENGALURU_CORRIDOR_GPS.get(r_id, {"lat": 12.9716, "lon": 77.5946})
                coords = [[gps["lat"], gps["lon"]], [gps["lat"] + 0.005, gps["lon"] + 0.005]]

            lanes = geo.get("lanes", 4)
            speed_limit = geo.get("speed_limit_kmh", 50.0)
            topo = (self.predictor.topology or {}).get(r_id, {})

            base_vol = float(topo.get("peak_volume" if hour in [8, 9, 17, 18, 19] else "avg_volume", 1450))
            base_spd = float(topo.get("peak_speed" if hour in [8, 9, 17, 18, 19] else "avg_speed", 28.0))
            current_los = topo.get("common_congestion", "Moderate")

            # Check dynamic event impact
            active_events = self.event_manager.find_active_events(road_id=r_id)
            if active_events:
                base_vol = round(base_vol * 1.25)
                base_spd = max(8.0, round(base_spd * 0.7, 1))
                current_los = "Severe" if current_los in ["High", "Severe"] else "High"

            features = {
                "city_zone": info.get("city_zone", "Downtown Core"),
                "road_id": r_id,
                "intersection_id": info.get("intersection_id", "INT_01"),
                "vehicle_count": base_vol,
                "average_speed": base_spd,
                "capacity_utilization": round(min(100.0, (base_vol / max(1000.0, lanes * 900.0)) * 100.0), 1),
                "congestion_level": current_los,
                "hour": hour,
                "day_of_week": dow,
                "is_weekend": is_weekend
            }

            # Model prediction
            try:
                _, prob_dist = self.predictor.predict_segment(features)
            except Exception:
                prob_dist = {"Low": 0.25, "Moderate": 0.50, "High": 0.15, "Severe": 0.10}

            weight, pred_los, interp_probs = self._calculate_prediction_weight(
                current_los=current_los,
                prob_dist=prob_dist,
                horizon_minutes=horizon_minutes
            )

            # Physically clamped density: k = min(150 veh/km/lane, q / v)
            clamped_spd = max(5.0, base_spd)
            density_k_per_lane = round(min(150.0, (base_vol / clamped_spd) / max(1, lanes)), 1)
            total_density_k = round(density_k_per_lane * lanes, 1)

            interpolated_pts = self._interpolate_polyline(coords, sub_divisions=3)
            sub_segments = []
            for idx, pt in enumerate(interpolated_pts):
                sub_segments.append({
                    "segment_idx": idx,
                    "lat": pt[0],
                    "lng": pt[1],
                    "weight": weight,
                    "density_k": density_k_per_lane,
                    "total_density_k": total_density_k,
                    "predicted_los": pred_los,
                    "prob_dist": interp_probs,
                    "speed_kmh": base_spd,
                    "speed_limit_kmh": speed_limit
                })

            traffic_segments.append({
                "road_id": r_id,
                "road_name": get_road_name(r_id),
                "city_zone": info.get("city_zone", "Central"),
                "lanes": lanes,
                "sub_segments": sub_segments,
                "primary_weight": weight,
                "predicted_los": pred_los
            })

        return traffic_segments

    def _compute_crowd_layer(self, hour: int) -> List[Dict[str, Any]]:
        """Computes pedestrian crowd hotspots across high-footfall metropolitan hubs."""
        crowd_hubs = [
            {
                "hub_id": "HUB_BLR_01",
                "name": "Majestic KSRTC & Metro Central Interchange",
                "city_zone": "Central Spine",
                "lat": 12.9774,
                "lng": 77.5708,
                "base_footfall_peds_hr": 2400,
                "walkway_area_sqm": 750.0,
                "connected_road_id": "RD_BLR_02",
                "vehicle_approach_speed_kmh": 22.0
            },
            {
                "hub_id": "HUB_BLR_02",
                "name": "Silk Board Bus Bay & Hosur Road Junction",
                "city_zone": "South Corridor",
                "lat": 12.9174,
                "lng": 77.6235,
                "base_footfall_peds_hr": 1950,
                "walkway_area_sqm": 600.0,
                "connected_road_id": "RD_BLR_11",
                "vehicle_approach_speed_kmh": 35.0
            },
            {
                "hub_id": "HUB_BLR_03",
                "name": "Indiranagar 100ft Road / CMH Metro Crosswalk",
                "city_zone": "East Corridor",
                "lat": 12.9784,
                "lng": 77.6408,
                "base_footfall_peds_hr": 1350,
                "walkway_area_sqm": 500.0,
                "connected_road_id": "RD_BLR_01",
                "vehicle_approach_speed_kmh": 28.0
            },
            {
                "hub_id": "HUB_BLR_04",
                "name": "Brigade Road & MG Road Retail Promenade",
                "city_zone": "Commercial Core",
                "lat": 12.9730,
                "lng": 77.6075,
                "base_footfall_peds_hr": 2800,
                "walkway_area_sqm": 850.0,
                "connected_road_id": "RD_BLR_18",
                "vehicle_approach_speed_kmh": 18.0
            },
            {
                "hub_id": "HUB_BLR_05",
                "name": "Electronic City Phase 1 Transit Toll Plaza",
                "city_zone": "Tech Park Spine",
                "lat": 12.8399,
                "lng": 77.6770,
                "base_footfall_peds_hr": 1600,
                "walkway_area_sqm": 700.0,
                "connected_road_id": "RD_BLR_20",
                "vehicle_approach_speed_kmh": 45.0
            },
            {
                "hub_id": "HUB_BLR_06",
                "name": "Hebbal Flyover & Ring Road Interchange Base",
                "city_zone": "North Corridor",
                "lat": 13.0358,
                "lng": 77.5970,
                "base_footfall_peds_hr": 1200,
                "walkway_area_sqm": 550.0,
                "connected_road_id": "RD_BLR_03",
                "vehicle_approach_speed_kmh": 48.0
            }
        ]

        # Diurnal footfall multiplier
        if 8 <= hour <= 10 or 17 <= hour <= 20:
            multiplier = 1.35
        elif 12 <= hour <= 15:
            multiplier = 1.05
        elif 21 <= hour <= 23:
            multiplier = 0.65
        else:
            multiplier = 0.25

        crowd_layer: List[Dict[str, Any]] = []
        for hub in crowd_hubs:
            peds_hr = int(hub["base_footfall_peds_hr"] * multiplier)
            # Instantaneous pedestrian presence estimated from 30s dwell time
            instant_peds = round((peds_hr / 3600.0) * 30.0)
            area = hub["walkway_area_sqm"]
            ped_density_sqm = round(instant_peds / area, 2)
            fruin_los = get_fruin_los(ped_density_sqm)

            # Vulnerable Road User (VRU) Conflict Index: combines density with vehicle speed
            v_spd = hub["vehicle_approach_speed_kmh"]
            vru_index = round(min(1.0, max(0.05, (ped_density_sqm / 2.0) * 0.6 + ((v_spd / 50.0) ** 2) * 0.4)), 3)

            crowd_layer.append({
                "hub_id": hub["hub_id"],
                "name": hub["name"],
                "city_zone": hub["city_zone"],
                "lat": hub["lat"],
                "lng": hub["lng"],
                "connected_road_id": hub["connected_road_id"],
                "pedestrians_per_hour": peds_hr,
                "active_pedestrian_cluster": instant_peds,
                "ped_density_sqm": ped_density_sqm,
                "fruin_los": fruin_los,
                "vru_conflict_index": vru_index,
                "weight": vru_index
            })

        return crowd_layer

    def _compute_junction_layer(self, hour: int, minute: int) -> List[Dict[str, Any]]:
        """Extracts complete Webster signal optimization telemetry for all 24 registered junctions."""
        junction_layer: List[Dict[str, Any]] = []

        for r_id, info in ROAD_REGISTRY.items():
            gps = BENGALURU_CORRIDOR_GPS.get(r_id, {"lat": 12.9716, "lon": 77.5946})
            int_id = info.get("intersection_id", f"INT_{r_id.replace('RD_', '')}")
            int_name = get_intersection_name(int_id) or info.get("intersection_name", r_id)

            try:
                j_tel = self.junction_service.get_junction_telemetry(road_id=r_id, hour=hour, minute=minute)
                approaches = j_tel.get("approaches", [])
                nb_app = approaches[0] if approaches else {}
                signals = j_tel.get("signals", {})

                q_meters = min(450.0, max(5.0, float(nb_app.get("queue_length_meters", 45.0))))
                q_veh = min(65.0, max(1.0, float(nb_app.get("queue_vehicles", 6.0))))
                delay_sec = float(nb_app.get("control_delay_sec", 24.0))
                hcm_los = str(nb_app.get("level_of_service", "LOS C (Stable Flow)"))
                sat_deg = float(nb_app.get("degree_of_saturation", 0.65))

                webster_c0 = float(signals.get("optimal_cycle_sec", 90.0))
                green_ns = float(signals.get("ns_green_sec", 45.0))
                green_ew = float(signals.get("ew_green_sec", 35.0))
                spillback = "Critical" if sat_deg >= 0.95 else "Moderate" if sat_deg >= 0.80 else "Minimal"

            except Exception:
                q_meters = 50.0
                q_veh = 7.0
                delay_sec = 28.0
                hcm_los = "LOS C"
                sat_deg = 0.65
                webster_c0 = 90.0
                green_ns = 45.0
                green_ew = 35.0
                spillback = "Minimal"

            junction_layer.append({
                "junction_id": int_id,
                "name": int_name,
                "road_id": r_id,
                "lat": gps["lat"],
                "lng": gps["lon"],
                "queue_meters": round(q_meters, 1),
                "queue_vehicles": round(q_veh, 1),
                "control_delay_sec": round(delay_sec, 1),
                "hcm_los": hcm_los,
                "degree_of_saturation": round(sat_deg, 2),
                "webster_cycle_sec": round(webster_c0, 1),
                "green_split_ns_sec": round(green_ns, 1),
                "green_split_ew_sec": round(green_ew, 1),
                "spillback_risk": spillback,
                "weight": round(min(1.0, max(0.2, sat_deg)), 3)
            })

        return junction_layer

    def get_tri_pillar_heatmap(self, horizon_minutes: int = 0, channel: str = "all") -> Dict[str, Any]:
        """
        Calculates unified tri-pillar heatmap payload across temporal horizons.
        """
        now_dt = datetime.datetime.now()
        horizon_minutes = max(0, min(60, int(horizon_minutes)))
        channel = str(channel).lower().strip()

        result: Dict[str, Any] = {
            "status": "success",
            "horizon_minutes": horizon_minutes,
            "timestamp": now_iso(),
            "provenance": {
                "source": "multi_channel_tri_pillar_engine",
                "traffic_model": "XGBoost 80-Tree Ensemble (hist)",
                "pedestrian_model": "Fruin Walkway LOS & VRU Conflict Formulation",
                "junction_model": "Webster Optimal Cycle & Akcelik Delay Formulation (IRC:93)"
            }
        }

        if channel in ["all", "traffic"]:
            result["traffic_layer"] = self._compute_traffic_layer(horizon_minutes, now_dt)

        if channel in ["all", "crowd"]:
            result["crowd_layer"] = self._compute_crowd_layer(now_dt.hour)

        if channel in ["all", "junctions", "junction"]:
            result["junction_layer"] = self._compute_junction_layer(now_dt.hour, now_dt.minute)

        return result

    def get_legacy_points_projection(self) -> Dict[str, Any]:
        """Backward-compatible projection for legacy /api/map/heatmap consumers with clamped density."""
        tri_data = self.get_tri_pillar_heatmap(horizon_minutes=0, channel="traffic")
        legacy_points: List[Dict[str, Any]] = []

        for corridor in tri_data.get("traffic_layer", []):
            r_id = corridor["road_id"]
            r_name = corridor["road_name"]
            for seg in corridor.get("sub_segments", []):
                legacy_points.append({
                    "lat": seg["lat"],
                    "lng": seg["lng"],
                    "weight": seg["weight"],
                    "intensity": seg["weight"],
                    "density_k": seg["density_k"],
                    "congestion": seg["predicted_los"],
                    "road_id": r_id,
                    "road_name": r_name,
                    "speed_kmh": seg["speed_kmh"],
                    "vehicle_count": int(seg["density_k"] * seg["speed_kmh"]),
                    "capacity_utilization": round(seg["weight"] * 100.0, 1),
                    "is_clamped_physical": True
                })

        return {
            "status": "success",
            "point_count": len(legacy_points),
            "max_weight": 1.0,
            "points": legacy_points,
            "timestamp": now_iso()
        }

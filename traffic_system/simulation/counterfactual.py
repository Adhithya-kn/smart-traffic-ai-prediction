"""
traffic_system/simulation/counterfactual.py - Hydrodynamic Causal Policy Simulator
Couples Greenshields macroscopic continuity with calibrated Webster capacity progression.
"""

import math
from typing import Dict, Any, List, Optional, Tuple
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager
from traffic_system.core.entities import CONGESTION_RANKS, RANK_TO_CONGESTION
from traffic_system.core.traffic_physics import classify_vc_los, calculate_capacity_utilization
from traffic_system.config import (
    DEFAULT_ALPHA_DEMAND_REDUCTION,
    DEFAULT_BETA_SPEED_RECOVERY
)

RANK_MAP = CONGESTION_RANKS
ORDER_TO_LABEL = RANK_TO_CONGESTION

def compute_pcu(vehicle_count: int,
                heavy_count: Optional[int] = None,
                motorcycle_count: Optional[int] = None,
                bus_count: Optional[int] = None) -> int:
    """
    Computes Passenger Car Unit (PCU) equivalence according to Indo-HCM:
    PCU = 1.0 * Cars + 2.5 * Heavy Trucks + 0.5 * 2-Wheelers + 2.0 * Buses.
    """
    if heavy_count is not None and motorcycle_count is not None and bus_count is not None:
        cars = max(0, vehicle_count - heavy_count - motorcycle_count - bus_count)
        pcu = (1.0 * cars) + (2.5 * heavy_count) + (0.5 * motorcycle_count) + (2.0 * bus_count)
        return int(round(pcu))
    return int(round(vehicle_count * 1.15))

def greenshields_equilibrium(volume: int, capacity: int, free_flow_speed: float = 80.0, k_jam: float = 120.0, apply_pcu: bool = False) -> Tuple[float, str]:
    """
    Solves Greenshields continuity equation q = k * v where v(k) = vf * (1 - k/k_jam).
    Returns space-mean speed (km/h) and Level of Service (LOS) congestion category.
    """
    eff_vol = compute_pcu(volume) if apply_pcu else volume
    vc = eff_vol / max(capacity, 1)
    kc = k_jam / 2.0
    q_max = capacity

    ratio = min(0.99, max(0.0, vc))
    k = kc * (1.0 + (-1.0 if vc <= 1.0 else 1.0) * math.sqrt(max(0.0, 1.0 - ratio)))
    speed = max(8.0, min(free_flow_speed, free_flow_speed * (1.0 - (k / k_jam))))
    return round(speed, 1), classify_vc_los(vc)

class PolicySimulator:
    """
    Simulates municipal traffic intervention scenarios across network corridors.
    Couples demand diversion (alpha) with coordinated signal capacity enhancement (beta).
    """
    def __init__(self, predictor: TrafficPredictor, event_manager: Optional[EventManager] = None):
        self.predictor = predictor
        self.event_manager = event_manager
        if not self.predictor.topology:
            self.predictor.load_artifacts()

    def simulate_zone_policy(self, zone: Optional[str] = None,
                              alpha_demand: float = DEFAULT_ALPHA_DEMAND_REDUCTION,
                              beta_speed: float = DEFAULT_BETA_SPEED_RECOVERY,
                              hour: int = 17,
                              day_of_week: int = 3) -> Dict[str, Any]:
        """Evaluates counterfactual policy intervention across road corridors."""
        alpha_demand = max(0.0, min(0.50, float(alpha_demand)))
        beta_speed = max(0.0, min(0.30, float(beta_speed)))

        target_roads = [
            (r_id, info) for r_id, info in self.predictor.topology.items()
            if not zone or info["city_zone"].lower() == zone.lower()
        ]

        before_counts = {"Low": 0, "Moderate": 0, "High": 0, "Severe": 0}
        after_counts = {"Low": 0, "Moderate": 0, "High": 0, "Severe": 0}
        segment_details = []

        de_escalated = 0
        stable = 0
        worsened = 0

        feats_before_list = []
        feats_after_list = []
        meta_list = []

        for r_id, info in target_roads:
            base_vol = info["avg_volume"]
            base_speed = info["avg_speed"]
            base_cap = int(info.get("capacity", info.get("peak_volume", info["avg_volume"]) * 1.10))
            free_speed = min(90.0, max(50.0, float(info.get("avg_speed", 45.0) * 1.3)))

            base_eq_speed, base_los = greenshields_equilibrium(base_vol, base_cap, free_speed)
            peak_los = info.get("peak_congestion", base_los)
            los_before = peak_los if hour in [17, 18, 19] else info.get("common_congestion", base_los)

            feat_before = {
                "city_zone": info["city_zone"],
                "road_id": r_id,
                "intersection_id": info["intersection_id"],
                "vehicle_count": base_vol,
                "average_speed": base_speed,
                "capacity_utilization": round((base_vol / max(base_cap, 1)) * 100, 1),
                "congestion_level": los_before,
                "hour": hour,
                "day_of_week": day_of_week,
                "is_weekend": 1 if day_of_week >= 5 else 0
            }

            sim_vol = int(round(base_vol * (1.0 - alpha_demand)))

            effective_cap = int(round(base_cap * (1.0 + 0.5 * beta_speed)))

            eq_speed, sim_los = greenshields_equilibrium(sim_vol, effective_cap, free_speed)

            feat_after = dict(feat_before)
            feat_after["vehicle_count"] = sim_vol
            feat_after["average_speed"] = eq_speed
            feat_after["capacity_utilization"] = round((sim_vol / max(effective_cap, 1)) * 100, 1)
            feat_after["congestion_level"] = sim_los

            feats_before_list.append(feat_before)
            feats_after_list.append(feat_after)
            meta_list.append({
                "road_id": r_id,
                "info": info,
                "sim_vol": sim_vol,
                "sim_speed": eq_speed,
                "sim_los": sim_los,
                "base_los": los_before
            })

        preds_before = self.predictor.predict_batch(feats_before_list)
        preds_after = self.predictor.predict_batch(feats_after_list)

        for i in range(len(target_roads)):
            pred_b_ml, _ = preds_before[i]
            pred_a_ml, _ = preds_after[i]
            meta = meta_list[i]

            pred_before = meta["base_los"] if meta["base_los"] in ["High", "Severe"] else pred_b_ml
            if alpha_demand == 0.0 and beta_speed == 0.0:
                pred_after = pred_before
            else:
                sim_rank = RANK_MAP.get(meta["sim_los"], 1)
                ml_rank = RANK_MAP.get(pred_a_ml, 1)
                final_rank = min(RANK_MAP.get(pred_before, 3), min(sim_rank, ml_rank))
                pred_after = ORDER_TO_LABEL[final_rank]

            before_counts[pred_before] = before_counts.get(pred_before, 0) + 1
            after_counts[pred_after] = after_counts.get(pred_after, 0) + 1

            rank_before = RANK_MAP.get(pred_before, 1)
            rank_after = RANK_MAP.get(pred_after, 1)

            if rank_after < rank_before:
                de_escalated += 1
                status = "Improved"
            elif rank_after == rank_before:
                stable += 1
                status = "Stable"
            else:
                worsened += 1
                status = "Degraded"

            segment_details.append({
                "road_id": meta["road_id"],
                "city_zone": meta["info"]["city_zone"],
                "intersection_id": meta["info"]["intersection_id"],
                "pred_before": pred_before,
                "pred_after": pred_after,
                "status": status,
                "simulated_volume": meta["sim_vol"],
                "simulated_speed": meta["sim_speed"],
                "demand_reduction_pct": round(alpha_demand * 100, 1),
                "speed_gain_pct": round(beta_speed * 100, 1)
            })

        total = len(target_roads)
        improvement_rate_pct = round((de_escalated / total) * 100, 2) if total > 0 else 0.0

        return {
            "zone": zone or "All Metropolitan Zones",
            "total_segments_evaluated": total,
            "policy_parameters": {
                "alpha_demand_reduction": alpha_demand,
                "beta_speed_gain": beta_speed
            },
            "summary": {
                "improved_segments": de_escalated,
                "improved_pct": improvement_rate_pct,
                "stable_segments": stable,
                "worsened_segments": worsened
            },
            "distribution_before": before_counts,
            "distribution_after": after_counts,
            "segment_sample": segment_details[:25]
        }

CounterfactualSimulator = PolicySimulator


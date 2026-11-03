"""
traffic_system/simulation/signal_optimizer.py - Webster & Akcelik Signal Optimization Engine
Implements F.V. Webster (1958) optimal signal cycle calculation and Akcelik/HCM delay models.
"""

import math
from typing import Dict, Any, Tuple

DEFAULT_SATURATION_FLOW_PCU = 1800.0
AMBER_TIME_SEC = 3.0
ALL_RED_TIME_SEC = 1.0
LOST_TIME_PER_PHASE_SEC = AMBER_TIME_SEC + ALL_RED_TIME_SEC

_HCM_LEVELS = (
    (10.0, "LOS A (Free Flow)"), (20.0, "LOS B (Reasonably Free)"),
    (35.0, "LOS C (Stable Flow)"), (55.0, "LOS D (Approaching Unstable)"),
    (80.0, "LOS E (Unstable / Capacity)")
)

def get_hcm_los(delay_sec: float) -> str:
    """Categorizes control delay into Highway Capacity Manual (HCM 2020) Level of Service."""
    return next((label for limit, label in _HCM_LEVELS if delay_sec <= limit), "LOS F (Forced Breakdown / Oversaturated)")

class WebsterSignalOptimizer:
    """
    Computes optimal traffic signal cycle length, directional phase splits,
    and delay evaluation using Webster (1958) and Akcelik (1980) queueing formulations.
    Formula: C_0 = (1.5 * L + 5) / (1 - Y)
    """

    def __init__(self, saturation_flow_per_lane: float = DEFAULT_SATURATION_FLOW_PCU):
        self.sat_flow = saturation_flow_per_lane

    def optimize_intersection_signals(
        self,
        ns_volume_pcu: float,
        ew_volume_pcu: float,
        ns_lanes: int = 2,
        ew_lanes: int = 2,
        phase_extension_sec: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculates Webster minimum-delay cycle time, green phase allocations,
        degree of saturation, approach queue lengths, and delay reduction.
        """
        lost_time_L = 2.0 * LOST_TIME_PER_PHASE_SEC

        s_ns = max(900.0, float(ns_lanes) * self.sat_flow)
        s_ew = max(900.0, float(ew_lanes) * self.sat_flow)

        y_ns = max(0.04, float(ns_volume_pcu) / s_ns)
        y_ew = max(0.04, float(ew_volume_pcu) / s_ew)

        Y = y_ns + y_ew
        Y_capped = min(0.88, max(0.12, Y))

        c0_unbounded = (1.5 * lost_time_L + 5.0) / (1.0 - Y_capped)
        optimal_cycle = round(min(135.0, max(45.0, c0_unbounded + phase_extension_sec)), 1)

        total_green = max(20.0, optimal_cycle - lost_time_L)

        split_ratio_ns = y_ns / Y if Y > 0 else 0.55
        ns_green = round(max(14.0, total_green * split_ratio_ns), 1)
        ew_green = round(max(10.0, total_green - ns_green), 1)

        lambda_ns = ns_green / optimal_cycle
        lambda_ew = ew_green / optimal_cycle

        x_ns = float(ns_volume_pcu) / (s_ns * lambda_ns) if lambda_ns > 0 else 1.0
        x_ew = float(ew_volume_pcu) / (s_ew * lambda_ew) if lambda_ew > 0 else 1.0

        optimized_delay_ns = self._estimate_delay(optimal_cycle, lambda_ns, x_ns, ns_volume_pcu, s_ns)
        baseline_cycle = 90.0
        baseline_lambda_ns = (45.0 - LOST_TIME_PER_PHASE_SEC) / baseline_cycle
        baseline_x_ns = float(ns_volume_pcu) / (s_ns * baseline_lambda_ns)
        baseline_delay_ns = self._estimate_delay(baseline_cycle, baseline_lambda_ns, baseline_x_ns, ns_volume_pcu, s_ns)

        delay_saved_per_veh = round(max(0.0, baseline_delay_ns - optimized_delay_ns), 1)

        red_ns = optimal_cycle - ns_green
        q_veh_ns = round(max(0.0, (ns_volume_pcu / 3600.0 * red_ns) / (1.0 - min(0.95, ns_volume_pcu / s_ns))), 1)
        queue_meters_ns = round(q_veh_ns * 6.5, 1)

        total_delay_saved_vph = round(delay_saved_per_veh * (ns_volume_pcu / 3600.0), 2)

        return {
            "optimal_cycle_sec": optimal_cycle,
            "ns_green_sec": ns_green,
            "ew_green_sec": ew_green,
            "amber_sec": AMBER_TIME_SEC,
            "all_red_sec": ALL_RED_TIME_SEC,
            "intersection_saturation_index": round(Y, 3),
            "degree_of_saturation_ns": round(x_ns, 2),
            "degree_of_saturation_ew": round(x_ew, 2),
            "estimated_delay_sec": round(optimized_delay_ns, 1),
            "delay_saved_sec": delay_saved_per_veh,
            "queue_vehicles_ns": q_veh_ns,
            "queue_meters_ns": queue_meters_ns,
            "total_delay_saved_vph": total_delay_saved_vph,
            "level_of_service": get_hcm_los(optimized_delay_ns),
            "coordination_mode": "ACTUATED_SPLIT_OPTIMIZED" if Y > 0.65 else "COORDINATED_PROGRESSION"
        }

    def _estimate_delay(self, C: float, lmbda: float, x: float, q: float, s: float) -> float:
        """
        Computes average intersection delay (seconds/vehicle) using Webster's uniform delay
        and Akcelik's time-dependent overflow queue formula (T = 0.25h).
        """
        lmbda = max(0.10, min(0.90, lmbda))
        c_cap = s * lmbda
        q_sec = max(0.01, q / 3600.0)

        denom1 = 2.0 * max(0.05, 1.0 - lmbda * min(1.0, x))
        term1 = (C * ((1.0 - lmbda) ** 2)) / denom1

        T = 0.25
        if x < 0.85:
            term2 = (x ** 2) / (2.0 * q_sec * max(0.05, 1.0 - x))
        else:
            term2 = 900.0 * T * ((x - 1.0) + math.sqrt((x - 1.0) ** 2 + (8.0 * 0.5 * x) / (max(10.0, c_cap) * T)))

        return min(150.0, max(4.0, term1 + term2))

"""
traffic_system/computer_vision/pcu_converter.py - Indo-HCM 2017 PCU Flow Normalizer
Converts heterogeneous urban vehicle mixtures into standardized Passenger Car Units (PCU)
according to Indian Highway Capacity Manual (Indo-HCM 2017) and IRC:SP:84-2019 standards.

Source & Academic Citations:
1. Indian Highway Capacity Manual (Indo-HCM 2017), CSIR-CRRI, New Delhi.
   Chapter 4 (Urban Roads), Table 4.1: Recommended PCU Equivalencies for Arterial Mid-Blocks.
2. Indian Roads Congress (IRC:SP:84-2019): Manual of Specifications and Standards for Four Laning of Highways.

PCU Factor Justifications & Applicability:
- car (1.00): Standard reference design passenger car unit (width ~1.8m, length ~4.5m).
- motorcycle / two_wheeler (0.50): Reduced transverse footprint, lane-splitting flexibility, rapid acceleration from standstill; occupies approx 1/2 of standard passenger car dynamic envelope.
- auto_rickshaw / three_wheeler (0.80): Maneuverable intermediate three-wheel footprint (width ~1.3m, length ~2.6m); moderate lateral clearance and acceleration.
- transit_bus (2.80): Large physical envelope (length ~12m, width ~2.6m), frequent curb-side deceleration/dwell delays, and substantial headway requirements.
- light_commercial / lcv (1.40): Small delivery vans and pickup trucks with intermediate payload inertia.
- truck / heavy_vehicle (3.00): High longitudinal footprint (length 10-15m), low acceleration dynamics, wide turning swept path.
"""

from typing import Dict, Any


# Standardized Indo-HCM 2017 Table 4.1 Equivalencies
INDO_HCM_PCU_FACTORS: Dict[str, float] = {
    "car": 1.00,
    "automobile": 1.00,
    "motorcycle": 0.50,
    "two_wheeler": 0.50,
    "bike": 0.50,
    "auto": 0.80,
    "auto_rickshaw": 0.80,
    "three_wheeler": 0.80,
    "bus": 2.80,
    "transit_bus": 2.80,
    "lcv": 1.40,
    "light_commercial": 1.40,
    "truck": 3.00,
    "heavy_vehicle": 3.00
}

CANONICAL_CLASSES = ["car", "motorcycle", "auto_rickshaw", "bus", "truck"]


class IndoHCMPCUConverter:
    """
    Normalizes multi-class urban traffic volume into standardized Passenger Car Units (PCU).
    Converts short video observation periods into extrapolated steady-state hourly rates
    with explicit documentation of steady-state assumptions.
    """

    @staticmethod
    def get_factor(class_name: str) -> float:
        """Returns PCU factor for a vehicle class, defaulting to 1.0 for unspecified vehicles."""
        norm_name = class_name.lower().replace("-", "_").strip()
        return INDO_HCM_PCU_FACTORS.get(norm_name, 1.00)

    @classmethod
    def calculate_total_pcu(cls, class_counts: Dict[str, int]) -> float:
        """Calculates aggregate PCU value across a vehicle count distribution."""
        total_pcu = 0.0
        for cname, count in class_counts.items():
            factor = cls.get_factor(cname)
            total_pcu += factor * count
        return round(total_pcu, 2)

    @classmethod
    def calculate_hourly_flow(cls, total_pcu: float, duration_seconds: float) -> float:
        """
        Extrapolates observation window PCU to standard hourly equivalent flow rate:
        q_hourly = (q_pcu / Δt_sec) * 3600 [PCU/hr].

        IMPORTANT SCIENTIFIC ASSUMPTION:
        This conversion mathematically extrapolates a short video window (e.g. 10-60 seconds)
        under the assumption that the sampled period reflects a steady-state stationary traffic stream.
        It is an extrapolated annualized/hourly rate, NOT an actual physical 60-minute continuous measurement.
        """
        sec = max(1.0, duration_seconds)
        hourly_rate = (total_pcu / sec) * 3600.0
        return round(hourly_rate, 1)

    @classmethod
    def get_flow_telemetry(cls, total_pcu: float, duration_seconds: float) -> Dict[str, Any]:
        """Returns structured hourly flow telemetry with explicit methodological metadata."""
        sec = max(1.0, duration_seconds)
        hourly_rate = (total_pcu / sec) * 3600.0
        return {
            "extrapolated_hourly_flow_pcu": round(hourly_rate, 1),
            "sample_duration_seconds": round(sec, 2),
            "is_actual_measured_hourly_flow": False,
            "flow_rate_type": "extrapolated_steady_state_hourly_rate",
            "steady_state_assumption": (
                "Assumes the short video observation window reflects a stationary, representative traffic stream. "
                "This is an annualized/hourly extrapolation, not an actual physical 60-minute continuous measurement."
            )
        }

    @classmethod
    def get_mix_breakdown(cls, class_counts: Dict[str, int]) -> Dict[str, Any]:
        """
        Returns disaggregated vehicle mix breakdown with individual counts, PCU contribution,
        and percentage composition of total roadway traffic.
        """
        total_raw = sum(class_counts.values())
        total_pcu = cls.calculate_total_pcu(class_counts)

        breakdown: Dict[str, Dict[str, Any]] = {}
        for cname, count in class_counts.items():
            factor = cls.get_factor(cname)
            pcu_subtotal = round(factor * count, 2)
            pct_raw = round((count / max(total_raw, 1)) * 100.0, 1)
            pct_pcu = round((pcu_subtotal / max(total_pcu, 0.01)) * 100.0, 1)

            breakdown[cname] = {
                "count": count,
                "pcu_factor": factor,
                "pcu_subtotal": pcu_subtotal,
                "percentage_raw": pct_raw,
                "percentage_pcu": pct_pcu,
                "indo_hcm_source": "Indo-HCM 2017 Table 4.1 (CSIR-CRRI)"
            }

        return {
            "total_raw_vehicles": total_raw,
            "total_pcu": total_pcu,
            "classes": breakdown
        }

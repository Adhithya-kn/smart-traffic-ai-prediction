"""
traffic_system/core/traffic_physics.py - Canonical Traffic Flow Dynamics & Metrics
Consolidates speed performance index, capacity utilization, BPR delay formulas,
and level of service (LOS) classifications with rigorous input range clamping (DRY Principle).
"""

from typing import Tuple


def calculate_spi(current_speed: float, free_flow_speed: float) -> float:
    """
    Calculates Speed Performance Index (SPI) as a percentage (0.0 to 100.0+).
    Input range clamped: current_speed >= 0.0, free_flow_speed >= 1.0.
    """
    spd = max(0.0, float(current_speed))
    ff_spd = max(1.0, float(free_flow_speed))
    return round((spd / ff_spd) * 100.0, 1)


def classify_spi_los(spi: float) -> str:
    """Categorizes Speed Performance Index into standard Level of Service."""
    val = max(0.0, float(spi))
    return "Low" if val >= 75.0 else "Moderate" if val >= 50.0 else "High" if val >= 30.0 else "Severe"


def classify_speed_los(speed: float) -> str:
    """Categorizes kinematic space-mean speed (km/h) into Level of Service."""
    s = max(0.0, float(speed))
    return "Low" if s >= 38.0 else "Moderate" if s >= 27.0 else "High" if s >= 18.0 else "Severe"


def classify_vc_los(vc_ratio: float) -> str:
    """Categorizes Volume-to-Capacity (V/C) ratio into Level of Service."""
    r = max(0.0, float(vc_ratio))
    return "Low" if r < 0.40 else "Moderate" if r < 0.70 else "High" if r < 0.90 else "Severe"


def calculate_capacity_utilization(volume: float, capacity: float, clamp: bool = True) -> float:
    """
    Calculates percentage of road design capacity currently utilized.
    Optionally clamps between 10.0% and 100.0% for model stability.
    """
    vol = max(0.0, float(volume))
    cap = max(1.0, float(capacity))
    raw = (vol / cap) * 100.0
    if clamp:
        return round(min(100.0, max(10.0, raw)), 1)
    return round(raw, 1)


def calculate_scaled_volume(baseline_volume: float, capacity_utilization_pct: float) -> int:
    """
    Scales derived volume against empirical baseline to maintain
    fidelity with the XGBoost training distribution (15,000 - 65,000).
    """
    b_vol = max(0.0, float(baseline_volume))
    cap_util = max(0.0, min(100.0, float(capacity_utilization_pct)))
    multiplier = 0.55 + (0.95 * (cap_util / 100.0))
    return int(round(b_vol * multiplier))


def bpr_travel_time(
    free_flow_time_sec: float,
    volume: float,
    capacity: float,
    alpha: float = 0.15,
    beta: float = 4.0
) -> float:
    """
    Bureau of Public Roads (BPR) link performance function:
    T = T_0 * [1 + alpha * (V / C)^beta]
    Returns estimated travel time in seconds.
    """
    t0 = max(1.0, float(free_flow_time_sec))
    vc = max(0.0, float(volume) / max(1.0, float(capacity)))
    return round(t0 * (1.0 + alpha * (vc ** beta)), 2)


def speed_to_travel_time_minutes(distance_km: float, speed_kmh: float) -> float:
    """Converts distance and speed into travel time in minutes."""
    d = max(0.0, float(distance_km))
    s = max(1.0, float(speed_kmh))
    return round((d / s) * 60.0, 2)

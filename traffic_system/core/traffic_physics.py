"""
traffic_system/core/traffic_physics.py - Canonical Traffic Flow Dynamics & Metrics
Consolidates speed performance index, capacity utilization, and level of service (LOS)
classifications across all prediction, simulation, and live ingestion pipelines (DRY Principle).
"""

from typing import Tuple

def calculate_spi(current_speed: float, free_flow_speed: float) -> float:
    """Calculates Speed Performance Index (SPI) as a percentage (0.0 to 100.0+)."""
    return round((float(current_speed) / max(float(free_flow_speed), 1.0)) * 100.0, 1)

def classify_spi_los(spi: float) -> str:
    """Categorizes Speed Performance Index into standard Level of Service."""
    return "Low" if spi >= 75.0 else "Moderate" if spi >= 50.0 else "High" if spi >= 30.0 else "Severe"

def classify_speed_los(speed: float) -> str:
    """Categorizes kinematic space-mean speed (km/h) into Level of Service."""
    s = float(speed)
    return "Low" if s >= 38.0 else "Moderate" if s >= 27.0 else "High" if s >= 18.0 else "Severe"

def classify_vc_los(vc_ratio: float) -> str:
    """Categorizes Volume-to-Capacity (V/C) ratio into Level of Service."""
    r = float(vc_ratio)
    return "Low" if r < 0.40 else "Moderate" if r < 0.70 else "High" if r < 0.90 else "Severe"

def calculate_capacity_utilization(volume: float, capacity: float, clamp: bool = True) -> float:
    """
    Calculates percentage of road design capacity currently utilized.
    Optionally clamps between 10.0% and 100.0% for model stability.
    """
    raw = (float(volume) / max(float(capacity), 1.0)) * 100.0
    if clamp:
        return round(min(100.0, max(10.0, raw)), 1)
    return round(raw, 1)

def calculate_scaled_volume(baseline_volume: float, capacity_utilization_pct: float) -> int:
    """
    Scales derived volume against empirical baseline to maintain
    fidelity with the XGBoost training distribution ($15,000 - $65,000).
    """
    multiplier = 0.55 + (0.95 * (float(capacity_utilization_pct) / 100.0))
    return int(round(float(baseline_volume) * multiplier))

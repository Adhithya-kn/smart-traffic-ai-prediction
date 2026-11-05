"""
traffic_system/core/traffic_physics.py - Canonical Traffic Flow Dynamics & Metrics
Consolidates speed performance index (SPI), capacity utilization, Bureau of Public Roads (BPR)
delay formulations, Greenshields macroscopic continuity, and level of service (LOS) classifications
with rigorous physical units, mathematical bounds, and input range clamping (DRY Principle).

Physical Units Standard:
- Speed: kilometers per hour (km/h)
- Space-Mean Speed: km/h
- Volume / Flow Rate (q): vehicles per hour (veh/h or vph) or Passenger Car Units per hour (PCU/h)
- Density (k): vehicles per kilometer (veh/km)
- Jam Density (k_jam): veh/km (typically 120 - 150 veh/km per lane)
- Distance: kilometers (km) or meters (m)
- Travel Time: seconds (sec) or minutes (min)
- Acceleration / Deceleration: meters per second squared (m/s^2)
"""

import math
from typing import Tuple


def calculate_spi(current_speed: float, free_flow_speed: float) -> float:
    """
    Calculates Speed Performance Index (SPI) as a percentage (0.0 to 100.0+).
    Formula: SPI = (v_current / v_free_flow) * 100%
    Units: current_speed (km/h), free_flow_speed (km/h).
    Clamped: current_speed >= 0.0, free_flow_speed >= 1.0.
    """
    spd = max(0.0, float(current_speed))
    ff_spd = max(1.0, float(free_flow_speed))
    return round((spd / ff_spd) * 100.0, 1)


def classify_spi_los(spi: float) -> str:
    """
    Categorizes Speed Performance Index into standard Level of Service:
    - >= 75%: Low (Free Flow)
    - 50% - 75%: Moderate (Stable Flow)
    - 30% - 50%: High (Approaching Unstable)
    - < 30%: Severe (Forced Breakdown)
    """
    val = max(0.0, float(spi))
    return "Low" if val >= 75.0 else "Moderate" if val >= 50.0 else "High" if val >= 30.0 else "Severe"


def classify_speed_los(speed: float) -> str:
    """
    Categorizes kinematic space-mean speed (km/h) into Level of Service:
    - >= 38.0 km/h: Low
    - 27.0 - 38.0 km/h: Moderate
    - 18.0 - 27.0 km/h: High
    - < 18.0 km/h: Severe
    """
    s = max(0.0, float(speed))
    return "Low" if s >= 38.0 else "Moderate" if s >= 27.0 else "High" if s >= 18.0 else "Severe"


def classify_vc_los(vc_ratio: float) -> str:
    """
    Categorizes Volume-to-Capacity (V/C) ratio into Level of Service:
    - < 0.40: Low
    - 0.40 - 0.70: Moderate
    - 0.70 - 0.90: High
    - >= 0.90: Severe
    """
    r = max(0.0, float(vc_ratio))
    return "Low" if r < 0.40 else "Moderate" if r < 0.70 else "High" if r < 0.90 else "Severe"


def calculate_capacity_utilization(volume: float, capacity: float, clamp: bool = True) -> float:
    """
    Calculates percentage of road design capacity currently utilized:
    Formula: Utilization (%) = (Volume / Capacity) * 100%
    Units: volume (veh/h), capacity (veh/h).
    Optionally clamps between 10.0% and 100.0% for model stability.
    """
    vol = max(0.0, float(volume))
    cap = max(1.0, float(capacity))
    raw = (vol / cap) * 100.0
    if clamp:
        return round(min(100.0, max(10.0, raw)), 1)
    return round(raw, 1)


# ---------------------------------------------------------------------------
# Measured-state mapping (Phase 2, ML workstream)
#
# The committed benchmark dataset is SYNTHETIC. Its target label was generated
# from the Travel Time Index by the following relation, which we recovered from
# the committed CSV (57,600 rows, R^2 = 0.999976, max residual 0.223):
#
#     Congestion Level = 45.0159 * Travel Time Index - 45.0286
#
# The predictor was trained with `congestion_level` as a *feature* produced by
# thresholding that score at <50 / <75 / <90. At inference time we do not have
# the dataset's `Congestion Level` column; the documented equivalent below
# reconstructs the same score from a measured speed and the corridor free-flow
# speed (TTI = free_flow_speed / measured_speed) and applies the identical
# thresholds. This is a proxy mapping tied to the synthetic label generator, NOT
# a physically calibrated Level of Service; forecasts must keep the PROXY label.
# ---------------------------------------------------------------------------
SYNTHETIC_CONGESTION_TTI_SLOPE = 45.0159
SYNTHETIC_CONGESTION_TTI_INTERCEPT = -45.0286
CONGESTION_SCORE_MIN = 5.0
CONGESTION_SCORE_MAX = 100.0
MAX_PLAUSIBLE_TRAVEL_TIME_INDEX = 8.0


def measured_capacity_utilization(flow_vph: float, design_capacity_vph: float) -> float:
    """
    Volume/capacity utilisation percentage for a MEASURED approach flow.

    Differs from :func:`calculate_capacity_utilization` in that it has no 10 %
    floor: a genuinely low measured flow must map to a low utilisation instead
    of being clamped up to 10 %. Values are bounded to [0, 100] because the
    training distribution never exceeds 100 %.

    Units: flow_vph (veh/h), design_capacity_vph (veh/h).
    """
    flow = float(flow_vph)
    if not math.isfinite(flow) or flow < 0:
        raise ValueError(f"flow_vph must be a finite value >= 0, got {flow_vph!r}")
    capacity = float(design_capacity_vph)
    if not math.isfinite(capacity) or capacity <= 0:
        raise ValueError(f"design_capacity_vph must be a finite value > 0, got {design_capacity_vph!r}")
    raw = (flow / capacity) * 100.0
    return round(min(100.0, max(0.0, raw)), 1)


def estimate_travel_time_index(speed_kmh: float, free_flow_speed_kmh: float) -> float:
    """
    Estimates TTI = free-flow travel time / observed travel time
    = free_flow_speed / observed_speed (same corridor, same distance).

    Clamped to [1.0, MAX_PLAUSIBLE_TRAVEL_TIME_INDEX] because TTI < 1 is not
    physical (a vehicle cannot beat free-flow) and extremely small speeds would
    otherwise dominate the derived congestion score.
    """
    speed = float(speed_kmh)
    free_flow = float(free_flow_speed_kmh)
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError(f"speed_kmh must be a finite value > 0, got {speed_kmh!r}")
    if not math.isfinite(free_flow) or free_flow <= 0:
        raise ValueError(
            f"free_flow_speed_kmh must be a finite value > 0, got {free_flow_speed_kmh!r}"
        )
    return round(min(MAX_PLAUSIBLE_TRAVEL_TIME_INDEX, max(1.0, free_flow / speed)), 4)


def synthetic_congestion_score_from_tti(travel_time_index: float) -> float:
    """
    Reconstructs the benchmark's synthetic congestion score from a TTI.

    Coefficients and bounds were recovered from the committed synthetic dataset
    (see the block comment above). The returned score is clipped to the
    benchmark's observed range [5, 100] so it cannot produce an out-of-range
    model feature.
    """
    tti = float(travel_time_index)
    if not math.isfinite(tti) or tti <= 0:
        raise ValueError(f"travel_time_index must be a finite value > 0, got {travel_time_index!r}")
    score = SYNTHETIC_CONGESTION_TTI_SLOPE * tti + SYNTHETIC_CONGESTION_TTI_INTERCEPT
    return round(min(CONGESTION_SCORE_MAX, max(CONGESTION_SCORE_MIN, score)), 3)


def congestion_level_from_score(congestion_score: float) -> str:
    """
    Applies the benchmark training-label thresholds to a congestion score:
    < 50 Low, < 75 Moderate, < 90 High, >= 90 Severe.

    Identical to the ``score_to_los`` mapping used when the model was trained, so
    the categorical feature stays inside the trained label space.
    """
    score = float(congestion_score)
    if score < 50.0:
        return "Low"
    if score < 75.0:
        return "Moderate"
    if score < 90.0:
        return "High"
    return "Severe"


def congestion_level_from_speed(speed_kmh: float, free_flow_speed_kmh: float) -> str:
    """
    Documented equivalent of the training-label derivation for a measured
    speed: TTI -> recovered synthetic congestion score -> training thresholds.

    Returns one of Low / Moderate / High / Severe. Callers must label the result
    as a proxy (it is not a measured physical LOS).
    """
    tti = estimate_travel_time_index(speed_kmh, free_flow_speed_kmh)
    return congestion_level_from_score(synthetic_congestion_score_from_tti(tti))


def calculate_scaled_volume(baseline_volume: float, capacity_utilization_pct: float) -> int:
    """
    Scales derived volume against empirical baseline to maintain
    fidelity with the XGBoost training distribution (15,000 - 65,000 veh/day or corridor aggregate).

    DEPRECATED for CV->forecast use: this is a static-baseline heuristic, not a
    measurement. It is retained only for the explicitly labelled live-telemetry
    fallback path.
    """
    b_vol = max(0.0, float(baseline_volume))
    cap_util = max(0.0, min(100.0, float(capacity_utilization_pct)))
    multiplier = 0.55 + (0.95 * (cap_util / 100.0))
    return int(round(b_vol * multiplier))


def greenshields_speed_from_density(
    density_k: float,
    free_flow_speed_vf: float = 60.0,
    jam_density_kj: float = 120.0
) -> float:
    """
    Greenshields linear speed-density relationship:
    v(k) = v_f * (1 - k / k_jam)
    Units:
    - density_k: veh/km
    - free_flow_speed_vf: km/h
    - jam_density_kj: veh/km
    Returns speed in km/h clamped between 0.0 and free_flow_speed_vf.
    """
    k = max(0.0, min(jam_density_kj, float(density_k)))
    vf = max(10.0, float(free_flow_speed_vf))
    kj = max(10.0, float(jam_density_kj))
    speed = vf * (1.0 - (k / kj))
    return round(max(0.0, speed), 2)


def greenshields_flow_from_density(
    density_k: float,
    free_flow_speed_vf: float = 60.0,
    jam_density_kj: float = 120.0
) -> float:
    """
    Greenshields fundamental flow equation:
    q = k * v(k) = k * v_f * (1 - k / k_jam)
    Units:
    - density_k: veh/km
    - free_flow_speed_vf: km/h
    - jam_density_kj: veh/km
    Returns flow rate q in veh/h (vph). Maximum occurs at critical density k_c = k_jam / 2.
    """
    k = max(0.0, min(jam_density_kj, float(density_k)))
    speed = greenshields_speed_from_density(k, free_flow_speed_vf, jam_density_kj)
    flow = k * speed
    return round(max(0.0, flow), 1)


def calculate_maximum_capacity(
    free_flow_speed_vf: float,
    jam_density_kj: float = 120.0,
    lanes: int = 1
) -> float:
    """
    Theoretical maximum highway capacity according to Greenshields model:
    q_max = (v_f * k_jam / 4) * lanes
    Units:
    - free_flow_speed_vf: km/h
    - jam_density_kj: veh/km
    - lanes: integer lane count
    Returns q_max in vehicles/hour (veh/h).
    """
    vf = max(10.0, float(free_flow_speed_vf))
    kj = max(10.0, float(jam_density_kj))
    num_lanes = max(1, int(lanes))
    q_max_per_lane = (vf * kj) / 4.0
    return round(q_max_per_lane * num_lanes, 1)


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
    Units:
    - free_flow_time_sec: seconds
    - volume: veh/h or PCU/h
    - capacity: veh/h or PCU/h
    - alpha: dimensionless calibration parameter (standard default 0.15)
    - beta: dimensionless congestion exponent (standard default 4.0)
    Returns estimated travel time in seconds.
    """
    t0 = max(1.0, float(free_flow_time_sec))
    vc = max(0.0, float(volume) / max(1.0, float(capacity)))
    return round(t0 * (1.0 + alpha * (vc ** beta)), 2)


def speed_to_travel_time_minutes(distance_km: float, speed_kmh: float) -> float:
    """
    Converts physical link distance and space-mean speed into travel time in minutes.
    Formula: T_min = (distance_km / speed_kmh) * 60.0
    Units:
    - distance_km: kilometers
    - speed_kmh: kilometers per hour
    Returns travel time in minutes.
    """
    d = max(0.0, float(distance_km))
    s = max(1.0, float(speed_kmh))
    return round((d / s) * 60.0, 2)

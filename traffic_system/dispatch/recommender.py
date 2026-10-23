"""
traffic_system/dispatch/recommender.py - Municipal Action Directives & VMS Dispatcher
Generates operational directives, dynamic VMS messages, and actuated Webster signal timings.
"""

from typing import Dict, Any, Optional
from traffic_system.simulation.signal_optimizer import WebsterSignalOptimizer
from traffic_system.core.road_registry import get_road_name, ROAD_REGISTRY

_optimizer = WebsterSignalOptimizer()

# Real-world Bangalore metropolitan alternate corridors for incident rerouting
BANGALORE_CORRIDOR_DETOURS: Dict[str, str] = {
    "RD_BLR_01": "CMH Road or Old Airport Road",
    "RD_BLR_02": "Cubbon Road or Kasturba Road",
    "RD_BLR_03": "Thanisandra Main Road or NH-44 Service Lanes",
    "RD_BLR_04": "Old Madras Road or Swami Vivekananda Road",
    "RD_BLR_05": "Outer Ring Road (ORR) via Nagavara",
    "RD_BLR_06": "Hosur Elevated Tollway or Bannerghatta Road",
    "RD_BLR_07": "Hoodi Junction or Varthur Road",
    "RD_BLR_08": "South End Circle or Kanakapura Road",
    "RD_BLR_09": "HAL Old Airport Road or Kundalahalli Gate",
    "RD_BLR_10": "Haralur Road or Harlur-Kudlu Link",
    "RD_BLR_11": "HSR Layout 14th Main or Madiwala Underpass",
    "RD_BLR_12": "Koramangala 80 Feet Road or Inner Ring Road",
    "RD_BLR_13": "RV Road or 9th Main Road",
    "RD_BLR_14": "MG Road or Residency Road",
    "RD_BLR_15": "Whitefield Main Road or Borewell Road",
    "RD_BLR_16": "Kanakapura Road or 24th Main Road",
    "RD_BLR_17": "100 Feet Road or Intermediate Ring Road",
    "RD_BLR_18": "MG Road or Richmond Road",
    "RD_BLR_19": "Hennur Bagalur Road or Bellary Road",
    "RD_BLR_20": "Electronic City Elevated Tollway or Bettadasanapura Link",
    "RD_BLR_21": "HAL Airport Road or Panathur Main Road",
    "RD_BLR_22": "Banashankari Ring Road or 9th Cross Road",
    "RD_BLR_23": "Koramangala 100 Feet Road or Sarjapur Link",
    "RD_BLR_24": "Sampige Road or CV Raman Road",
}

def generate_action_directive(
    road_id: str,
    zone: str,
    congestion: str,
    has_active_event: bool = False,
    event_name: str = "",
    volume_vph: Optional[int] = None,
    lanes: int = 2
) -> Dict[str, Any]:
    """
    Generates municipal action directive, Webster signal override, and dynamic VMS message.
    Grounded in Bangalore metropolitan corridors with actionable tactical dispatch pillars.
    """
    cong_lower = congestion.strip().lower()
    road_name = get_road_name(road_id)
    detour = BANGALORE_CORRIDOR_DETOURS.get(road_id, "Adjacent Parallel Arterials")
    intersection = ROAD_REGISTRY.get(road_id, {}).get("intersection_name", f"{road_name} Intersection")

    if cong_lower == "severe":
        code = "DIR-SEV-01"
        priority = "URGENT_PRIORITY_1"
        dataset_action = "Priority review: investigate incidents, coordinate signals, evaluate alternative routes and improve public transport options"
        field_ops = f"Deploy BTP Traffic Warden at {intersection}. Enforce heavy commercial vehicle (HTV) restriction."
        signal_ops = "Activate dynamic Webster phase extension (+15s green). Coordinated green-wave progression."
        advisory_ops = f"Broadcast diversion to {detour}. Expect 25-35 min corridor delay."
        action = f"PRIORITY DISPATCH: {field_ops} {signal_ops} {advisory_ops}"
        vms = f"ALERT: SEVERE DELAYS ON {road_name} [{road_id}]. DIVERT VIA {detour.upper()}."
        ext_sec = 15.0
        cycle_mode = "DYNAMIC_COORDINATED"
        est_vol = volume_vph if volume_vph else 1885

    elif cong_lower == "high":
        code = "DIR-HIGH-02"
        priority = "ELEVATED_PRIORITY_2"
        dataset_action = "Review signal timing, peak-hour demand management and alternative routes"
        field_ops = f"Station roving motorcycle patrol along {road_name}. Clear kerbside bottlenecks."
        signal_ops = "Adjust split-adaptive signal timing (+8s green extension to primary mainline)."
        advisory_ops = f"Recommend {detour} for cross-zone commuters. Expect 15-20 min delay."
        action = f"ELEVATED CONTROL: {field_ops} {signal_ops} {advisory_ops}"
        vms = f"CAUTION: HEAVY TRAFFIC ON {road_name} [{road_id}]. EXPECT 15-20 MIN DELAYS. ALT: {detour.upper()}."
        ext_sec = 8.0
        cycle_mode = "SPLIT_ADAPTIVE"
        est_vol = volume_vph if volume_vph else 1359

    elif cong_lower in ["moderate", "medium"]:
        code = "DIR-MOD-03"
        priority = "STANDARD_PRIORITY_3"
        dataset_action = "Monitor traffic and review signal coordination"
        field_ops = "Automated AI camera surveillance active; automated queue monitoring."
        signal_ops = "Maintain standard coordinated signal offset (zero phase bias)."
        advisory_ops = "Standard commuter flow; no diversions required."
        action = f"COORDINATED MONITORING: {field_ops} {signal_ops} {advisory_ops}"
        vms = f"NORMAL FLOW WITH MODERATE DENSITY ON {road_name} [{road_id}]."
        ext_sec = 0.0
        cycle_mode = "STANDARD_OFFSET"
        est_vol = volume_vph if volume_vph else 703

    else:
        code = "DIR-LOW-04"
        priority = "ROUTINE_MONITORING"
        dataset_action = "Continue regular traffic monitoring"
        field_ops = "Routine automated surveillance active."
        signal_ops = "Energy-conserving actuated cycle active."
        advisory_ops = "Free-flow corridor passage."
        action = f"ROUTINE MONITORING: {field_ops} {signal_ops} {advisory_ops}"
        vms = f"SMOOTH TRAFFIC ON {road_name} [{road_id}]. ALL CLEAR."
        ext_sec = 0.0
        cycle_mode = "ENERGY_SAVING"
        est_vol = volume_vph if volume_vph else 177

    if has_active_event:
        event_notice = f" [ACTIVE EVENT NOTICE: {event_name} - Coordinate crowd management with city police.]"
        action += event_notice
        vms += f" [EVENT: {event_name.upper()}]"

    # Compute Actuated Webster Cycle Optimization
    webster_result = _optimizer.optimize_intersection_signals(
        ns_volume_pcu=float(est_vol),
        ew_volume_pcu=float(est_vol) * 0.65,
        ns_lanes=lanes,
        ew_lanes=max(1, lanes - 1),
        phase_extension_sec=ext_sec
    )

    signal_override = {
        "phase_extension_sec": int(ext_sec),
        "cycle_offset": cycle_mode,
        "optimal_cycle_sec": webster_result["optimal_cycle_sec"],
        "ns_green_sec": webster_result["ns_green_sec"],
        "ew_green_sec": webster_result["ew_green_sec"],
        "estimated_delay_saved_sec": webster_result["delay_saved_sec"],
        "saturation_index": webster_result["intersection_saturation_index"]
    }

    return {
        "directive_code": code,
        "priority_level": priority,
        "road_id": road_id,
        "road_name": road_name,
        "city_zone": zone,
        "congestion_state": congestion,
        "dataset_standard_action": dataset_action,
        "operational_action": action,
        "vms_broadcast_message": vms,
        "signal_actuation_parameters": signal_override,
        "tactical_breakdown": {
            "field_operations": field_ops,
            "signal_control": signal_ops,
            "traveler_advisory": advisory_ops,
            "recommended_detour": detour
        }
    }

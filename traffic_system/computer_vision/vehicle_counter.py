"""
traffic_system/computer_vision/vehicle_counter.py - Route-to-Route Transition & Unique Vehicle Counter
Accumulates unique vehicle counts across video duration by tracking ID and canonical vehicle class.
Supports car, motorcycle, bicycle, bus, and truck.
Strictly excludes pedestrians and unverified unknown objects from vehicle totals (no car fallback).
Maintains persistent track class identity and separates frame-level from cumulative counts.
Implements Virtual Gate Route Transition Flow Analysis:
- Gate A (Route Ingress) -> Gate B (Route Egress) transition tracking.
- Cumulative route-to-route completed transitions.
- Inter-arrival headway (seconds between vehicle arrivals).
- Transit frequency (vehicles per minute / vehicles per hour).
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from traffic_system.computer_vision.schemas import DetectionBox

CANONICAL_VEHICLE_CLASSES = ("car", "motorcycle", "bicycle", "bus", "truck", "auto_rickshaw", "lcv")


def _calc_median(values: List[float]) -> float:
    """Calculates median of a list of floats without external dependencies."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return float((s[mid - 1] + s[mid]) / 2.0)


class VehicleCounter:
    """
    Counts unique vehicle instances across temporal video frames using persistent track IDs.
    Separates counts by canonical categories: car, motorcycle, bicycle, bus, and truck.
    Preserves class identity throughout each tracklet to prevent flickering or misclassification.
    Computes trajectory vectors to categorize vehicular flow into directional channels (inbound vs outbound).
    Tracks route-to-route transitions from Gate A (ingress) to Gate B (egress) to measure inter-arrival
    frequency and route transition capacity.
    """
    def __init__(
        self,
        min_displacement_pixels: float = 15.0,
        min_hits: int = 1,
        gate_a_pct: float = 0.38,
        gate_b_pct: float = 0.80,
        route_name: str = "Route A -> Route B"
    ):
        self.min_displacement_pixels = min_displacement_pixels
        self.min_hits = max(1, int(min_hits))
        self.gate_a_pct = float(gate_a_pct)
        self.gate_b_pct = float(gate_b_pct)
        self.route_name = route_name

        # Route transition state
        self.route_transitions_count: int = 0
        self.route_transitions_by_class: Dict[str, int] = {c: 0 for c in CANONICAL_VEHICLE_CLASSES}
        self.completed_transits: List[Dict[str, Any]] = []
        self.headways: List[float] = []
        self.transit_durations: List[float] = []
        self._last_transition_time: Optional[float] = None
        self._max_timestamp: float = 0.0

        # Map: track_id -> {"class_name": str, "entry_pt": (x, y), "latest_pt": (x, y), ...}
        self.seen_tracks: Dict[int, Dict[str, Any]] = {}
        self.class_counts: Dict[str, int] = {c: 0 for c in CANONICAL_VEHICLE_CLASSES}
        self.direction_counts: Dict[str, int] = {
            "inbound": 0,
            "outbound": 0,
            "lateral": 0,
            "stationary": 0
        }
        self.class_direction_counts: Dict[str, Dict[str, int]] = {
            c: {"inbound": 0, "outbound": 0, "lateral": 0, "stationary": 0}
            for c in CANONICAL_VEHICLE_CLASSES
        }

        # Dynamic arbitrary directional tripwires and passage logging
        self.tripwires: List[Any] = []
        self.passage_events: List[Dict[str, Any]] = []
        self.tripwire_counts: Dict[str, Dict[str, Any]] = {}

        # Pedestrian crowd tracking
        self.pedestrian_count: int = 0

    def update_pedestrian_counts(self, detections: List[DetectionBox]) -> None:
        """Accumulates active pedestrian detections in current frame for crowd density analysis."""
        peds = [d for d in detections if getattr(d, "class_name", "") in ("pedestrian", "person")]
        self.pedestrian_count += len(peds)

    def get_crowd_density(self, roi_area_sqm: float = 100.0) -> Dict[str, Any]:
        """Calculates pedestrian crowd density and Fruin Walkway Level of Service."""
        area = max(1.0, float(roi_area_sqm))
        density_sqm = round(self.pedestrian_count / area, 3)
        if density_sqm <= 0.35:
            los = "LOS A (Free Flow)"
        elif density_sqm <= 0.65:
            los = "LOS B (Normal Walking)"
        elif density_sqm <= 1.05:
            los = "LOS C (Moderate Friction)"
        elif density_sqm <= 1.55:
            los = "LOS D (Restricted Flow)"
        elif density_sqm <= 2.25:
            los = "LOS E (Severe Crowding)"
        else:
            los = "LOS F (Breakdown / Crush)"
        return {
            "pedestrian_count": self.pedestrian_count,
            "area_sqm": area,
            "density_sqm": density_sqm,
            "fruin_los": los
        }

    def add_tripwire(self, tripwire: Any) -> None:
        """Registers a VectorTripwire for line-crossing counting and passage telemetry."""
        self.tripwires.append(tripwire)
        if tripwire.name not in self.tripwire_counts:
            self.tripwire_counts[tripwire.name] = {
                "total": 0,
                "classes": {c: 0 for c in CANONICAL_VEHICLE_CLASSES}
            }

    def get_passage_events(self) -> List[Dict[str, Any]]:
        """Returns all recorded vehicle passage events across all tripwires."""
        return list(self.passage_events)

    def get_tripwire_counts(self) -> Dict[str, Dict[str, Any]]:
        """Returns cumulative totals and class breakdowns per registered tripwire."""
        return {k: {"total": v["total"], "classes": dict(v["classes"])} for k, v in self.tripwire_counts.items()}

    def _determine_direction(self, entry_pt: Tuple[float, float], latest_pt: Tuple[float, float]) -> str:
        """Determines movement direction vector from vehicle trajectory."""
        dx = latest_pt[0] - entry_pt[0]
        dy = latest_pt[1] - entry_pt[1]
        dist = math.sqrt(dx ** 2 + dy ** 2)

        if dist < self.min_displacement_pixels:
            return "stationary"

        if abs(dy) >= abs(dx):
            return "inbound" if dy > 0 else "outbound"
        else:
            return "lateral"

    @staticmethod
    def normalize_vehicle_class(class_name: str) -> Optional[str]:
        """Normalizes class names and filters out non-vehicle classes (pedestrians, unknown)."""
        if not class_name or not isinstance(class_name, str):
            return None
        cname = class_name.lower().replace("-", "_").strip()
        if cname in ("bike", "motorbike", "motor_bike", "scooter", "two_wheeler"):
            return "motorcycle"
        if cname in ("cycle", "pedal_cycle"):
            return "bicycle"
        if cname in ("automobile", "taxi", "suv", "sedan", "van"):
            return "car"
        if cname in ("minibus", "transit_bus"):
            return "bus"
        if cname in ("pickup", "lorry", "heavy_truck"):
            return "truck"
        if cname in ("auto", "auto_rickshaw", "autorickshaw", "tuk_tuk", "three_wheeler", "auto_rickshaws"):
            return "auto_rickshaw"
        if cname in ("lcv", "tempo", "mini_truck", "pickup_van", "tata_ace"):
            return "lcv"
        if cname in CANONICAL_VEHICLE_CLASSES:
            return cname
        return None

    def update(
        self,
        detections: List[DetectionBox],
        timestamp_sec: float = 0.0,
        frame_width: int = 1280,
        frame_height: int = 720
    ) -> Dict[str, Any]:
        """
        Processes detections from current frame, registers new track IDs upon confirmation,
        evaluates virtual gate crossings (Route A Ingress -> Route B Egress),
        updates trajectory directional vectors, and returns current frame and cumulative statistics.
        """
        if timestamp_sec > self._max_timestamp:
            self._max_timestamp = timestamp_sec

        gate_a_x = frame_width * self.gate_a_pct
        gate_b_x = frame_width * self.gate_b_pct

        current_frame_classes: Dict[str, int] = {c: 0 for c in CANONICAL_VEHICLE_CLASSES}
        current_frame_vehicle_count = 0

        for det in detections:
            norm_cname = self.normalize_vehicle_class(det.class_name)
            # Exclude pedestrians and unknown objects from vehicle counts
            if norm_cname is None:
                continue

            current_frame_classes[norm_cname] += 1
            current_frame_vehicle_count += 1

            if det.track_id is not None:
                t_id = det.track_id
                center = ((det.x1 + det.x2) / 2.0, (det.y1 + det.y2) / 2.0)
                cx = center[0]

                if t_id not in self.seen_tracks:
                    is_counted = (self.min_hits <= 1)
                    init_gate_a_time = timestamp_sec if cx >= gate_a_x else None
                    init_status = "IN_TRANSIT" if init_gate_a_time is not None else "APPROACHING"

                    self.seen_tracks[t_id] = {
                        "class_name": norm_cname,
                        "entry_pt": center,
                        "latest_pt": center,
                        "direction": "stationary",
                        "hits": 1,
                        "counted": is_counted,
                        "gate_a_crossed_time": init_gate_a_time,
                        "gate_b_crossed_time": None,
                        "transit_completed": False,
                        "transit_duration_sec": None,
                        "route_status": init_status
                    }
                    if is_counted:
                        self.class_counts[norm_cname] += 1
                else:
                    rec = self.seen_tracks[t_id]
                    prev_pt = rec["latest_pt"]
                    rec["latest_pt"] = center
                    rec["hits"] += 1

                    # Refine class identity if consensus evolved
                    if norm_cname != rec["class_name"] and norm_cname in CANONICAL_VEHICLE_CLASSES:
                        if rec["counted"]:
                            old_c = rec["class_name"]
                            if self.class_counts[old_c] > 0:
                                self.class_counts[old_c] -= 1
                            self.class_counts[norm_cname] += 1
                        rec["class_name"] = norm_cname

                    track_cname = rec["class_name"]

                    # Evaluate Registered Vector Tripwire Crossings
                    if self.tripwires and prev_pt != center:
                        for tw in self.tripwires:
                            crossing = tw.check_crossing(prev_pt, center)
                            if crossing:
                                crossed_set = rec.setdefault("crossed_tripwires", set())
                                tw_key = f"{tw.name}_{crossing}"
                                if tw_key not in crossed_set:
                                    crossed_set.add(tw_key)
                                    ev = {
                                        "passage_id": f"pass_{tw.name}_{t_id}_{int(timestamp_sec * 1000)}",
                                        "track_id": t_id,
                                        "class_name": track_cname,
                                        "tripwire_name": tw.name,
                                        "direction": crossing,
                                        "timestamp_sec": round(timestamp_sec, 2),
                                        "speed_kmh": round(float(getattr(det, "speed_kmh", 0.0) or 0.0), 1),
                                        "frame_idx": getattr(det, "frame_idx", 0)
                                    }
                                    self.passage_events.append(ev)
                                    if tw.name not in self.tripwire_counts:
                                        self.tripwire_counts[tw.name] = {
                                            "total": 0,
                                            "classes": {c: 0 for c in CANONICAL_VEHICLE_CLASSES}
                                        }
                                    self.tripwire_counts[tw.name]["total"] += 1
                                    self.tripwire_counts[tw.name]["classes"][track_cname] = (
                                        self.tripwire_counts[tw.name]["classes"].get(track_cname, 0) + 1
                                    )

                    # Track confirmed for counting once observed in >= min_hits frames
                    if not rec["counted"] and rec["hits"] >= self.min_hits:
                        rec["counted"] = True
                        self.class_counts[track_cname] += 1

                    # Evaluate Virtual Gate Crossings: Route A -> Route B
                    if rec["gate_a_crossed_time"] is None and cx >= gate_a_x:
                        rec["gate_a_crossed_time"] = timestamp_sec
                        rec["route_status"] = "IN_TRANSIT"

                    if (
                        rec["gate_a_crossed_time"] is not None
                        and not rec["transit_completed"]
                        and cx >= gate_b_x
                    ):
                        rec["gate_b_crossed_time"] = timestamp_sec
                        rec["transit_completed"] = True
                        rec["route_status"] = "TRANSIT_COMPLETE"
                        duration = max(0.0, timestamp_sec - rec["gate_a_crossed_time"])
                        rec["transit_duration_sec"] = duration

                        headway = (
                            max(0.1, timestamp_sec - self._last_transition_time)
                            if self._last_transition_time is not None
                            else max(0.1, timestamp_sec)
                        )
                        self._last_transition_time = timestamp_sec
                        self.headways.append(headway)
                        self.transit_durations.append(duration)
                        self.route_transitions_count += 1
                        self.route_transitions_by_class[track_cname] += 1
                        self.completed_transits.append({
                            "track_id": t_id,
                            "class_name": track_cname,
                            "transit_time_sec": round(timestamp_sec, 2),
                            "duration_sec": round(duration, 2),
                            "headway_sec": round(headway, 2)
                        })

                    # Re-evaluate directional vector as trajectory lengthens
                    old_dir = rec["direction"]
                    new_dir = self._determine_direction(rec["entry_pt"], rec["latest_pt"])
                    if new_dir != old_dir and rec["counted"]:
                        if old_dir in self.direction_counts and self.direction_counts[old_dir] > 0:
                            self.direction_counts[old_dir] -= 1
                            if old_dir in self.class_direction_counts[track_cname]:
                                self.class_direction_counts[track_cname][old_dir] -= 1
                        self.direction_counts[new_dir] += 1
                        self.class_direction_counts[track_cname][new_dir] += 1
                        rec["direction"] = new_dir
                    elif not rec["counted"] and new_dir != old_dir:
                        rec["direction"] = new_dir

                # Set route status attribute on detection for HUD rendering
                rec = self.seen_tracks[t_id]
                if hasattr(det, "route_status"):
                    det.route_status = rec.get("route_status", "APPROACHING")

        total_counted = sum(1 for r in self.seen_tracks.values() if r["counted"])
        elapsed = max(self._max_timestamp, 1.0)
        vpm = round((self.route_transitions_count / elapsed) * 60.0, 1)
        avg_headway = round(sum(self.headways) / len(self.headways), 1) if self.headways else 0.0

        return {
            "current_frame_total": current_frame_vehicle_count,
            "current_frame_classes": current_frame_classes,
            "cumulative_unique_total": total_counted,
            "cumulative_classes": dict(self.class_counts),
            "cumulative_directions": dict(self.direction_counts),
            "route_transitions_count": self.route_transitions_count,
            "transit_frequency_vpm": vpm,
            "average_headway_sec": avg_headway
        }

    def get_summary(self) -> Dict[str, Any]:
        """Returns total unique count, class breakdown, directional flow counts, and route transition flow."""
        total_counted = sum(1 for r in self.seen_tracks.values() if r["counted"])
        elapsed = max(self._max_timestamp, 1.0)
        vpm = round((self.route_transitions_count / elapsed) * 60.0, 1)
        vph = round(vpm * 60.0, 0)
        avg_headway = round(sum(self.headways) / len(self.headways), 1) if self.headways else 0.0
        median_dur = round(_calc_median(self.transit_durations), 1)

        return {
            "total_unique_vehicles": total_counted,
            "class_counts": dict(self.class_counts),
            "direction_counts": dict(self.direction_counts),
            "class_direction_counts": {k: dict(v) for k, v in self.class_direction_counts.items()},
            "tripwire_counts": self.get_tripwire_counts(),
            "passage_events": list(self.passage_events),
            "route_flow": {
                "route_name": self.route_name,
                "transitions_count": self.route_transitions_count,
                "transit_frequency_vpm": vpm,
                "transit_frequency_vph": vph,
                "average_headway_sec": avg_headway,
                "median_transit_duration_sec": median_dur,
                "transitions_by_class": dict(self.route_transitions_by_class),
                "completed_transits": list(self.completed_transits)
            }
        }

    def reset(self) -> None:
        """Resets counter accumulators."""
        self.seen_tracks.clear()
        for k in self.class_counts:
            self.class_counts[k] = 0
        for k in self.direction_counts:
            self.direction_counts[k] = 0
        for c in self.class_direction_counts:
            for d in self.class_direction_counts[c]:
                self.class_direction_counts[c][d] = 0
        self.route_transitions_count = 0
        self.route_transitions_by_class = {c: 0 for c in CANONICAL_VEHICLE_CLASSES}
        self.completed_transits.clear()
        self.headways.clear()
        self.transit_durations.clear()
        self.passage_events.clear()
        for k in self.tripwire_counts:
            self.tripwire_counts[k]["total"] = 0
            for c in self.tripwire_counts[k]["classes"]:
                self.tripwire_counts[k]["classes"][c] = 0
        self._last_transition_time = None
        self._max_timestamp = 0.0

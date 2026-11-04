"""
traffic_system/computer_vision/vehicle_counter.py - Unique & Directional Vehicle Counter
Accumulates unique vehicle counts across video duration by tracking ID and canonical vehicle class.
Supports car, motorcycle, bicycle, bus, and truck.
Strictly excludes pedestrians and unverified unknown objects from vehicle totals (no car fallback).
Maintains persistent track class identity and separates frame-level from cumulative counts.
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from traffic_system.computer_vision.schemas import DetectionBox

CANONICAL_VEHICLE_CLASSES = ("car", "motorcycle", "bicycle", "bus", "truck")


class VehicleCounter:
    """
    Counts unique vehicle instances across temporal video frames using persistent track IDs.
    Separates counts by canonical categories: car, motorcycle, bicycle, bus, and truck.
    Preserves class identity throughout each tracklet to prevent flickering or misclassification.
    Computes trajectory vectors to categorize vehicular flow into directional channels (inbound vs outbound).
    """
    def __init__(self, min_displacement_pixels: float = 15.0, min_hits: int = 1):
        self.min_displacement_pixels = min_displacement_pixels
        self.min_hits = max(1, int(min_hits))
        # Map: track_id -> {"class_name": str, "entry_pt": (x, y), "latest_pt": (x, y), "direction": str, "hits": int, "counted": bool}
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
        cname = class_name.lower().replace("-", "_").strip()
        if cname in ("bike",):
            return "motorcycle"
        if cname in ("cycle",):
            return "bicycle"
        if cname in CANONICAL_VEHICLE_CLASSES:
            return cname
        return None

    def update(self, detections: List[DetectionBox]) -> Dict[str, Any]:
        """
        Processes detections from current frame, registers new track IDs upon confirmation,
        updates trajectory directional vectors, and returns current frame and cumulative statistics.
        """
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

                if t_id not in self.seen_tracks:
                    is_counted = (self.min_hits <= 1)
                    self.seen_tracks[t_id] = {
                        "class_name": norm_cname,
                        "entry_pt": center,
                        "latest_pt": center,
                        "direction": "stationary",
                        "hits": 1,
                        "counted": is_counted
                    }
                    if is_counted:
                        self.class_counts[norm_cname] += 1
                else:
                    rec = self.seen_tracks[t_id]
                    # Preserve established class identity throughout track
                    track_cname = rec["class_name"]
                    rec["latest_pt"] = center
                    rec["hits"] += 1

                    # Track confirmed for counting once observed in >= min_hits frames
                    if not rec["counted"] and rec["hits"] >= self.min_hits:
                        rec["counted"] = True
                        self.class_counts[track_cname] += 1

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

        total_counted = sum(1 for r in self.seen_tracks.values() if r["counted"])

        return {
            "current_frame_total": current_frame_vehicle_count,
            "current_frame_classes": current_frame_classes,
            "cumulative_unique_total": total_counted,
            "cumulative_classes": dict(self.class_counts),
            "cumulative_directions": dict(self.direction_counts)
        }

    def get_summary(self) -> Dict[str, Any]:
        """Returns total unique count, class breakdown, and directional flow counts."""
        total_counted = sum(1 for r in self.seen_tracks.values() if r["counted"])
        return {
            "total_unique_vehicles": total_counted,
            "class_counts": dict(self.class_counts),
            "direction_counts": dict(self.direction_counts),
            "class_direction_counts": {k: dict(v) for k, v in self.class_direction_counts.items()}
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

"""
traffic_system/computer_vision/vehicle_counter.py - Unique & Directional Vehicle Counter
Accumulates unique vehicle counts across video duration by tracking ID and vehicle class.
Provides direction-based counting (inbound, outbound, directional quadrants) to track traffic flow splits.
Filters unconfirmed single-frame tracks to eliminate duplicate or phantom counts.
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from traffic_system.computer_vision.schemas import DetectionBox


class VehicleCounter:
    """
    Counts unique vehicle instances across temporal video frames using persistent track IDs.
    Separates counts by canonical categories: car, motorcycle, bus, and truck.
    Computes trajectory vectors to categorize vehicular flow into directional channels (inbound vs outbound).
    """
    def __init__(self, min_displacement_pixels: float = 15.0, min_hits: int = 1):
        self.min_displacement_pixels = min_displacement_pixels
        self.min_hits = max(1, int(min_hits))
        # Map: track_id -> {"class_name": str, "entry_pt": (x, y), "latest_pt": (x, y), "direction": str, "hits": int}
        self.seen_tracks: Dict[int, Dict[str, Any]] = {}
        self.class_counts: Dict[str, int] = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0
        }
        self.direction_counts: Dict[str, int] = {
            "inbound": 0,
            "outbound": 0,
            "lateral": 0,
            "stationary": 0
        }
        self.class_direction_counts: Dict[str, Dict[str, int]] = {
            "car": {"inbound": 0, "outbound": 0, "lateral": 0, "stationary": 0},
            "motorcycle": {"inbound": 0, "outbound": 0, "lateral": 0, "stationary": 0},
            "bus": {"inbound": 0, "outbound": 0, "lateral": 0, "stationary": 0},
            "truck": {"inbound": 0, "outbound": 0, "lateral": 0, "stationary": 0}
        }

    def _determine_direction(self, entry_pt: Tuple[float, float], latest_pt: Tuple[float, float]) -> str:
        """Determines movement direction vector from vehicle trajectory."""
        dx = latest_pt[0] - entry_pt[0]
        dy = latest_pt[1] - entry_pt[1]
        dist = math.sqrt(dx ** 2 + dy ** 2)

        if dist < self.min_displacement_pixels:
            return "stationary"

        # Check dominant axis
        if abs(dy) >= abs(dx):
            return "inbound" if dy > 0 else "outbound"
        else:
            return "lateral"

    def update(self, detections: List[DetectionBox]) -> Dict[str, Any]:
        """
        Processes detections from current frame, registers new track IDs upon confirmation,
        updates trajectory directional vectors, and returns current frame statistics.
        """
        current_frame_classes: Dict[str, int] = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0
        }

        for det in detections:
            cname = det.class_name.lower().replace("-", "_").strip()
            if cname not in current_frame_classes:
                cname = "car"  # Default fallback
            current_frame_classes[cname] += 1

            if det.track_id is not None:
                t_id = det.track_id
                center = ((det.x1 + det.x2) / 2.0, (det.y1 + det.y2) / 2.0)

                if t_id not in self.seen_tracks:
                    # New track initialized
                    is_counted = (self.min_hits <= 1)
                    self.seen_tracks[t_id] = {
                        "class_name": cname,
                        "entry_pt": center,
                        "latest_pt": center,
                        "direction": "stationary",
                        "hits": 1,
                        "counted": is_counted
                    }
                    if is_counted:
                        if cname in self.class_counts:
                            self.class_counts[cname] += 1
                        else:
                            self.class_counts["car"] += 1
                else:
                    rec = self.seen_tracks[t_id]
                    rec["latest_pt"] = center
                    rec["hits"] += 1

                    # Track confirmed for counting once observed in >= min_hits frames
                    if not rec["counted"] and rec["hits"] >= self.min_hits:
                        rec["counted"] = True
                        if cname in self.class_counts:
                            self.class_counts[cname] += 1
                        else:
                            self.class_counts["car"] += 1

                    # Re-evaluate directional vector as trajectory lengthens
                    old_dir = rec["direction"]
                    new_dir = self._determine_direction(rec["entry_pt"], rec["latest_pt"])
                    if new_dir != old_dir and rec["counted"]:
                        if old_dir in self.direction_counts and self.direction_counts[old_dir] > 0:
                            self.direction_counts[old_dir] -= 1
                            if old_dir in self.class_direction_counts[cname]:
                                self.class_direction_counts[cname][old_dir] -= 1
                        self.direction_counts[new_dir] += 1
                        self.class_direction_counts[cname][new_dir] += 1
                        rec["direction"] = new_dir
                    elif not rec["counted"] and new_dir != old_dir:
                        rec["direction"] = new_dir

        total_counted = sum(1 for r in self.seen_tracks.values() if r["counted"])

        return {
            "current_frame_total": len(detections),
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

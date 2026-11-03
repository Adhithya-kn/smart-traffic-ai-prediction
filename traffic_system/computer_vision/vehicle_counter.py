"""
traffic_system/computer_vision/vehicle_counter.py - Unique Vehicle Counter
Accumulates unique vehicle counts across video duration by tracking ID and vehicle class.
Supports cars, motorcycles, buses, and trucks.
"""

from typing import List, Dict, Any, Set
from traffic_system.computer_vision.schemas import DetectionBox


class VehicleCounter:
    """
    Counts unique vehicle instances across temporal video frames using persistent track IDs.
    Separates counts by canonical categories: car, motorcycle, bus, and truck.
    """
    def __init__(self):
        self.seen_tracks: Dict[int, str] = {}
        self.class_counts: Dict[str, int] = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0
        }

    def update(self, detections: List[DetectionBox]) -> Dict[str, Any]:
        """
        Processes detections from current frame, registers any newly observed track IDs,
        and returns current frame statistics.
        """
        current_frame_classes: Dict[str, int] = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0
        }

        for det in detections:
            cname = det.class_name.lower()
            if cname in current_frame_classes:
                current_frame_classes[cname] += 1

            if det.track_id is not None and det.track_id not in self.seen_tracks:
                self.seen_tracks[det.track_id] = cname
                if cname in self.class_counts:
                    self.class_counts[cname] += 1
                else:
                    self.class_counts["car"] += 1

        return {
            "current_frame_total": len(detections),
            "current_frame_classes": current_frame_classes,
            "cumulative_unique_total": len(self.seen_tracks),
            "cumulative_classes": dict(self.class_counts)
        }

    def get_summary(self) -> Dict[str, Any]:
        """Returns total unique count and breakdown by vehicle class."""
        return {
            "total_unique_vehicles": len(self.seen_tracks),
            "class_counts": dict(self.class_counts)
        }

    def reset(self) -> None:
        """Resets counter accumulators."""
        self.seen_tracks.clear()
        for k in self.class_counts:
            self.class_counts[k] = 0

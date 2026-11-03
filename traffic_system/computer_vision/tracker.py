"""
traffic_system/computer_vision/tracker.py - Multi-Object Vehicle Tracker
ByteTrack-compatible IoU association algorithm tracking vehicles across consecutive frames
and assigning persistent unique track IDs.
"""

from typing import List, Dict, Any, Optional
from traffic_system.computer_vision.schemas import DetectionBox


def calculate_iou(box1: DetectionBox, box2: DetectionBox) -> float:
    """Calculates Intersection-over-Union (IoU) between two bounding boxes."""
    x_left = max(box1.x1, box2.x1)
    y_top = max(box1.y1, box2.y1)
    x_right = min(box1.x2, box2.x2)
    y_bottom = min(box1.y2, box2.y2)

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    intersection = (x_right - x_left) * (y_bottom - y_top)
    area1 = (box1.x2 - box1.x1) * (box1.y2 - box1.y1)
    area2 = (box2.x2 - box2.x1) * (box2.y2 - box2.y1)
    union = area1 + area2 - intersection

    return intersection / union if union > 0.0 else 0.0


class Tracklet:
    """Represents a continuous trajectory of an individual vehicle."""
    def __init__(self, track_id: int, initial_box: DetectionBox):
        self.track_id = track_id
        self.class_name = initial_box.class_name
        self.class_id = initial_box.class_id
        self.box = initial_box
        self.lost_frames = 0
        self.total_hits = 1

    def update(self, new_box: DetectionBox):
        self.box = new_box
        self.lost_frames = 0
        self.total_hits += 1


class VehicleTracker:
    """
    IoU-based Multi-Object Tracker assigning persistent tracking IDs to vehicles.
    Maintains track history, resolves identity switches, and prunes stale tracks.
    """
    def __init__(self, iou_threshold: float = 0.30, max_lost_frames: int = 30):
        self.iou_threshold = iou_threshold
        self.max_lost_frames = max_lost_frames
        self.tracks: Dict[int, Tracklet] = {}
        self._next_id = 1

    def update(self, detections: List[DetectionBox]) -> List[DetectionBox]:
        """
        Associates current frame detections with existing active tracks.
        Assigns track_id to each detection and returns updated detection list.
        """
        matched_tracks = set()
        matched_detections = set()

        # Compute IoU matrix between active tracks and current detections
        track_ids = list(self.tracks.keys())
        matches = []
        for d_idx, det in enumerate(detections):
            for t_id in track_ids:
                iou = calculate_iou(self.tracks[t_id].box, det)
                if iou >= self.iou_threshold:
                    matches.append((iou, d_idx, t_id))

        # Sort matches by highest IoU first (Greedy bipartite matching)
        matches.sort(key=lambda x: -x[0])
        for iou, d_idx, t_id in matches:
            if d_idx not in matched_detections and t_id not in matched_tracks:
                matched_detections.add(d_idx)
                matched_tracks.add(t_id)
                self.tracks[t_id].update(detections[d_idx])
                detections[d_idx].track_id = t_id

        # Initialize new tracks for unmatched detections
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_detections:
                new_id = self._next_id
                self._next_id += 1
                det.track_id = new_id
                self.tracks[new_id] = Tracklet(new_id, det)

        # Increment lost frames for unmatched tracks and prune dead ones
        dead_tracks = []
        for t_id in track_ids:
            if t_id not in matched_tracks:
                self.tracks[t_id].lost_frames += 1
                if self.tracks[t_id].lost_frames > self.max_lost_frames:
                    dead_tracks.append(t_id)

        for t_id in dead_tracks:
            del self.tracks[t_id]

        return detections

    def reset(self) -> None:
        """Resets tracker state."""
        self.tracks.clear()
        self._next_id = 1

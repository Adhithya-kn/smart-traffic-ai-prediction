"""
traffic_system/computer_vision/tracker.py - Multi-Object Vehicle Tracker
Custom two-stage IoU association algorithm tracking vehicles across consecutive frames.
Assigns persistent unique track IDs, validates ID persistence, recovers lost tracks,
prevents ID switches, and filters spurious single-frame detections to prevent duplicate counting.
(Note: Custom IoU association implementation, not official ByteTrack).
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from traffic_system.computer_vision.schemas import DetectionBox
from traffic_system.computer_vision.speed_estimator import SpeedEstimator


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


class TrackState(str, Enum):
    NEW = "NEW"
    TRACKED = "TRACKED"
    LOST = "LOST"
    REMOVED = "REMOVED"


class Tracklet:
    """Represents a continuous trajectory and state of an individual vehicle."""
    def __init__(self, track_id: int, initial_box: DetectionBox, frame_idx: int = 0):
        self.track_id = track_id
        self.class_name = initial_box.class_name
        self.class_id = initial_box.class_id
        self.box = initial_box
        self.state = TrackState.NEW
        self.start_frame = frame_idx
        self.last_seen_frame = frame_idx
        self.lost_frames = 0
        self.total_hits = 1
        self.is_confirmed = False
        self.speed_kmh = 0.0

        # Store trailing trajectory centroids (last 30 points)
        cx = (initial_box.x1 + initial_box.x2) / 2.0
        cy = (initial_box.y1 + initial_box.y2) / 2.0
        self.trajectory: List[Tuple[float, float]] = [(round(cx, 1), round(cy, 1))]
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.class_votes: Dict[str, float] = {
            initial_box.class_name: float(initial_box.confidence or 1.0)
        }

    def update(self, new_box: DetectionBox, frame_idx: int, speed_kmh: float = 0.0):
        # Accumulate confidence-weighted votes to determine consensus class and prevent misclassification flicker
        c_name = new_box.class_name or self.class_name
        self.class_votes[c_name] = self.class_votes.get(c_name, 0.0) + float(new_box.confidence or 1.0)
        best_class = max(self.class_votes.items(), key=lambda x: x[1])[0]
        self.class_name = best_class
        new_box.class_name = best_class
        new_box.class_id = self.class_id

        self.box = new_box
        self.state = TrackState.TRACKED
        self.lost_frames = 0
        self.total_hits += 1
        self.last_seen_frame = frame_idx
        self.speed_kmh = speed_kmh
        if self.total_hits >= 2:
            self.is_confirmed = True

        cx = (new_box.x1 + new_box.x2) / 2.0
        cy = (new_box.y1 + new_box.y2) / 2.0
        new_pt = (round(cx, 1), round(cy, 1))

        if self.trajectory:
            self.vx = new_pt[0] - self.trajectory[-1][0]
            self.vy = new_pt[1] - self.trajectory[-1][1]

        self.trajectory.append(new_pt)
        if len(self.trajectory) > 30:
            self.trajectory.pop(0)

    def predict_box(self) -> DetectionBox:
        """Projects bounding box forward using velocity vector during momentary occlusion."""
        if self.lost_frames == 0 or (self.vx == 0.0 and self.vy == 0.0):
            return self.box
        shift_x = self.vx * min(self.lost_frames, 5)
        shift_y = self.vy * min(self.lost_frames, 5)
        return DetectionBox(
            x1=self.box.x1 + shift_x,
            y1=self.box.y1 + shift_y,
            x2=self.box.x2 + shift_x,
            y2=self.box.y2 + shift_y,
            confidence=self.box.confidence,
            class_id=self.class_id,
            class_name=self.class_name,
            track_id=self.track_id
        )

    def mark_lost(self):
        self.lost_frames += 1
        self.state = TrackState.LOST


class VehicleTracker:
    """
    Two-stage IoU association tracker assigning persistent tracking IDs to vehicles.
    Stage 1: Primary association with high IoU threshold for currently tracked vehicles.
    Stage 2: Recovery association for lost tracks to bridge momentary occlusions and prevent ID switches.
    Filters unconfirmed single-frame detections to eliminate duplicate counting.
    """
    def __init__(
        self,
        iou_threshold: float = 0.30,
        recovery_iou_threshold: float = 0.18,
        max_lost_frames: int = 30,
        min_hits_to_confirm: int = 2,
        speed_estimator: Optional[SpeedEstimator] = None
    ):
        self.iou_threshold = iou_threshold
        self.recovery_iou_threshold = recovery_iou_threshold
        self.max_lost_frames = max_lost_frames
        self.min_hits_to_confirm = min_hits_to_confirm
        self.speed_estimator = speed_estimator if speed_estimator is not None else SpeedEstimator()

        self.tracks: Dict[int, Tracklet] = {}
        self._next_id = 1

        # Diagnostic tracker metrics
        self.id_switches_prevented: int = 0
        self.lost_tracks_recovered: int = 0
        self.total_tracks_created: int = 0

    def update(
        self,
        detections: List[DetectionBox],
        frame_idx: int = 0,
        fps: float = 30.0
    ) -> List[DetectionBox]:
        """
        Associates current frame detections with existing active and lost tracks.
        Assigns track_id, trajectory, and speed_kmh to each detection and returns updated detection list.
        """
        matched_tracks = set()
        matched_detections = set()

        # Separate active and lost tracks
        active_ids = [t_id for t_id, t in self.tracks.items() if t.state in (TrackState.TRACKED, TrackState.NEW)]
        lost_ids = [t_id for t_id, t in self.tracks.items() if t.state == TrackState.LOST]

        # Stage 1: Greedy bipartite matching against active tracks with standard threshold
        matches_stage1 = []
        for d_idx, det in enumerate(detections):
            for t_id in active_ids:
                track = self.tracks[t_id]
                iou = calculate_iou(track.box, det)
                if det.class_name == track.class_name and iou >= self.iou_threshold:
                    matches_stage1.append((iou, d_idx, t_id))
                elif (
                    det.class_name != "pedestrian"
                    and track.class_name != "pedestrian"
                    and iou >= max(self.iou_threshold, 0.35)
                ):
                    # Cross-category vehicle association (prevents duplicate tracks on YOLO class fluctuation)
                    matches_stage1.append((iou * 0.90, d_idx, t_id))
                elif iou >= (self.iou_threshold + 0.25):
                    self.id_switches_prevented += 1

        matches_stage1.sort(key=lambda x: -x[0])
        for iou, d_idx, t_id in matches_stage1:
            if d_idx not in matched_detections and t_id not in matched_tracks:
                matched_detections.add(d_idx)
                matched_tracks.add(t_id)

                speed = self.speed_estimator.estimate_speed(t_id, detections[d_idx], frame_idx, fps)
                self.tracks[t_id].update(detections[d_idx], frame_idx=frame_idx, speed_kmh=speed)

                detections[d_idx].track_id = t_id
                detections[d_idx].speed_kmh = speed
                detections[d_idx].trajectory = list(self.tracks[t_id].trajectory)

        # Stage 2: Recovery matching for remaining detections against LOST tracks
        unmatched_dets = [d_idx for d_idx in range(len(detections)) if d_idx not in matched_detections]
        if unmatched_dets and lost_ids:
            matches_stage2 = []
            for d_idx in unmatched_dets:
                det = detections[d_idx]
                for t_id in lost_ids:
                    track = self.tracks[t_id]
                    predicted_box = track.predict_box()
                    iou = calculate_iou(predicted_box, det)
                    if det.class_name == track.class_name and iou >= self.recovery_iou_threshold:
                        matches_stage2.append((iou, d_idx, t_id))
                    elif (
                        det.class_name != "pedestrian"
                        and track.class_name != "pedestrian"
                        and iou >= max(self.recovery_iou_threshold, 0.25)
                    ):
                        matches_stage2.append((iou * 0.90, d_idx, t_id))

            matches_stage2.sort(key=lambda x: -x[0])
            for iou, d_idx, t_id in matches_stage2:
                if d_idx not in matched_detections and t_id not in matched_tracks:
                    matched_detections.add(d_idx)
                    matched_tracks.add(t_id)
                    self.lost_tracks_recovered += 1

                    speed = self.speed_estimator.estimate_speed(t_id, detections[d_idx], frame_idx, fps)
                    self.tracks[t_id].update(detections[d_idx], frame_idx=frame_idx, speed_kmh=speed)

                    detections[d_idx].track_id = t_id
                    detections[d_idx].speed_kmh = speed
                    detections[d_idx].trajectory = list(self.tracks[t_id].trajectory)

        # Stage 3: Initialize new tracks for remaining unmatched detections
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_detections:
                new_id = self._next_id
                self._next_id += 1
                self.total_tracks_created += 1

                det.track_id = new_id
                speed = self.speed_estimator.estimate_speed(new_id, det, frame_idx, fps)
                det.speed_kmh = speed

                new_track = Tracklet(new_id, det, frame_idx=frame_idx)
                new_track.speed_kmh = speed
                self.tracks[new_id] = new_track
                det.trajectory = list(new_track.trajectory)

        # Stage 4: Mark unmatched tracks as LOST and prune dead tracks exceeding max_lost_frames
        dead_tracks = []
        for t_id, track in self.tracks.items():
            if t_id not in matched_tracks:
                track.mark_lost()
                if track.lost_frames > self.max_lost_frames:
                    dead_tracks.append(t_id)

        for t_id in dead_tracks:
            del self.tracks[t_id]

        return detections

    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns tracker health, association metrics, and recovery statistics."""
        active = sum(1 for t in self.tracks.values() if t.state == TrackState.TRACKED)
        lost = sum(1 for t in self.tracks.values() if t.state == TrackState.LOST)
        confirmed = sum(1 for t in self.tracks.values() if t.is_confirmed)
        return {
            "tracker_type": "CustomIoUAssociationTracker",
            "active_tracks": active,
            "lost_tracks": lost,
            "confirmed_tracks": confirmed,
            "total_tracks_created": self.total_tracks_created,
            "lost_tracks_recovered": self.lost_tracks_recovered,
            "id_switches_prevented": self.id_switches_prevented
        }

    def reset(self) -> None:
        """Resets tracker state, counters, and speed estimator."""
        self.tracks.clear()
        self._next_id = 1
        self.id_switches_prevented = 0
        self.lost_tracks_recovered = 0
        self.total_tracks_created = 0
        self.speed_estimator.reset()

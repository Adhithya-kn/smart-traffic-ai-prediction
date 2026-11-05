"""
traffic_system/computer_vision/bytetrack.py - ByteTrack Multi-Object Association Engine
Implements ByteTrack association with an 8-state linear Kalman Filter.
Associates both high- and low-confidence detections across two stages to preserve
track persistence during stop-and-go congestion and temporary occlusions.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from traffic_system.computer_vision.schemas import DetectionBox
from traffic_system.computer_vision.kalman_filter import KalmanBoxFilter, xyah_to_xyxy
from traffic_system.computer_vision.speed_estimator import SpeedEstimator


def calculate_iou_boxes(box1: DetectionBox, box2: DetectionBox) -> float:
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


class ByteTracklet:
    """Represents a continuous vehicle track with an 8-state Kalman Filter."""
    def __init__(self, track_id: int, initial_box: DetectionBox, frame_idx: int = 0):
        self.track_id = track_id
        self.class_name = initial_box.class_name
        self.class_id = initial_box.class_id
        self.state = TrackState.NEW
        self.start_frame = frame_idx
        self.last_seen_frame = frame_idx
        self.lost_frames = 0
        self.total_hits = 1
        self.is_confirmed = False
        self.speed_kmh = 0.0

        self.kf = KalmanBoxFilter()
        raw_box = np.array([initial_box.x1, initial_box.y1, initial_box.x2, initial_box.y2], dtype=np.float64)
        self.mean, self.cov = self.kf.initiate(raw_box)

        cx = (initial_box.x1 + initial_box.x2) / 2.0
        cy = (initial_box.y1 + initial_box.y2) / 2.0
        self.trajectory: List[Tuple[float, float]] = [(round(cx, 1), round(cy, 1))]
        self.class_votes: Dict[str, float] = {
            initial_box.class_name: float(initial_box.confidence or 1.0)
        }

    def predict(self) -> None:
        """Projects Kalman state forward under constant velocity."""
        self.mean, self.cov = self.kf.predict(self.mean, self.cov)

    def update(self, new_box: DetectionBox, frame_idx: int, speed_kmh: float = 0.0) -> None:
        """Updates Kalman filter state with new detection box."""
        raw_box = np.array([new_box.x1, new_box.y1, new_box.x2, new_box.y2], dtype=np.float64)
        self.mean, self.cov = self.kf.update(self.mean, self.cov, raw_box)

        c_name = new_box.class_name or self.class_name
        self.class_votes[c_name] = self.class_votes.get(c_name, 0.0) + float(new_box.confidence or 1.0)
        best_class = max(self.class_votes.items(), key=lambda x: x[1])[0]
        self.class_name = best_class
        new_box.class_name = best_class

        self.state = TrackState.TRACKED
        self.lost_frames = 0
        self.total_hits += 1
        self.last_seen_frame = frame_idx
        self.speed_kmh = speed_kmh
        if self.total_hits >= 2:
            self.is_confirmed = True

        cx = (new_box.x1 + new_box.x2) / 2.0
        cy = (new_box.y1 + new_box.y2) / 2.0
        self.trajectory.append((round(cx, 1), round(cy, 1)))
        if len(self.trajectory) > 40:
            self.trajectory.pop(0)

    def mark_lost(self) -> None:
        self.lost_frames += 1
        self.state = TrackState.LOST

    @property
    def box(self) -> DetectionBox:
        """Projects current Kalman mean into a DetectionBox."""
        return self.to_detection_box()

    def to_detection_box(self) -> DetectionBox:
        """Projects current Kalman mean into a DetectionBox."""
        xyxy = xyah_to_xyxy(self.mean)
        return DetectionBox(
            x1=float(xyxy[0]),
            y1=float(xyxy[1]),
            x2=float(xyxy[2]),
            y2=float(xyxy[3]),
            confidence=0.9,
            class_id=self.class_id,
            class_name=self.class_name,
            track_id=self.track_id
        )


class ByteTrackVehicleTracker:
    """
    ByteTrack multi-object association engine for vehicle tracking.
    Uses two-stage matching:
    1. Associate high-confidence detections with active Kalman-predicted tracks.
    2. Associate remaining unmatched active tracks with low-confidence detections.
    3. Recover lost tracks from remaining unmatched high-confidence detections.
    """
    def __init__(
        self,
        high_conf_thresh: float = 0.45,
        low_conf_thresh: float = 0.15,
        match_thresh: float = 0.30,
        recovery_thresh: float = 0.20,
        max_lost_frames: int = 30,
        min_hits_to_confirm: int = 2,
        speed_estimator: Optional[SpeedEstimator] = None
    ):
        self.high_conf_thresh = high_conf_thresh
        self.low_conf_thresh = low_conf_thresh
        self.match_thresh = match_thresh
        self.recovery_thresh = recovery_thresh
        self.max_lost_frames = max_lost_frames
        self.min_hits_to_confirm = min_hits_to_confirm
        self.speed_estimator = speed_estimator if speed_estimator is not None else SpeedEstimator()

        self.tracks: Dict[int, ByteTracklet] = {}
        self._next_id = 1
        self.total_tracks_created = 0
        self.lost_tracks_recovered = 0
        self.id_switches_prevented = 0

    def update(
        self,
        detections: List[DetectionBox],
        frame_idx: int = 0,
        fps: float = 30.0
    ) -> List[DetectionBox]:
        """
        Executes ByteTrack two-stage matching and updates all tracklets.
        Returns list of matched DetectionBox objects with assigned track_ids.
        """
        # Step 1: Predict next state for all active and lost tracks
        for track in self.tracks.values():
            track.predict()

        # Step 2: Separate high and low confidence detections
        dets_high_idx = []
        dets_low_idx = []
        for i, d in enumerate(detections):
            conf = float(d.confidence or 0.0)
            if conf >= self.high_conf_thresh:
                dets_high_idx.append(i)
            elif conf >= self.low_conf_thresh:
                dets_low_idx.append(i)

        active_track_ids = [t_id for t_id, t in self.tracks.items() if t.state in (TrackState.TRACKED, TrackState.NEW)]
        lost_track_ids = [t_id for t_id, t in self.tracks.items() if t.state == TrackState.LOST]

        matched_tracks = set()
        matched_dets = set()
        output_detections: List[DetectionBox] = []

        # Step 3: First Stage Association (Detections High with Active Tracks)
        matches_stage1 = []
        for d_idx in dets_high_idx:
            det = detections[d_idx]
            for t_id in active_track_ids:
                track = self.tracks[t_id]
                pred_box = track.to_detection_box()
                iou = calculate_iou_boxes(pred_box, det)
                if det.class_name == track.class_name and iou >= self.match_thresh:
                    matches_stage1.append((iou, d_idx, t_id))
                elif det.class_name != "pedestrian" and track.class_name != "pedestrian" and iou >= max(self.match_thresh, 0.35):
                    matches_stage1.append((iou * 0.90, d_idx, t_id))

        matches_stage1.sort(key=lambda x: -x[0])
        for iou, d_idx, t_id in matches_stage1:
            if d_idx not in matched_dets and t_id not in matched_tracks:
                matched_dets.add(d_idx)
                matched_tracks.add(t_id)

                speed = self.speed_estimator.estimate_speed(t_id, detections[d_idx], frame_idx, fps)
                self.tracks[t_id].update(detections[d_idx], frame_idx=frame_idx, speed_kmh=speed)

                detections[d_idx].track_id = t_id
                detections[d_idx].speed_kmh = speed
                detections[d_idx].trajectory = list(self.tracks[t_id].trajectory)
                output_detections.append(detections[d_idx])

        # Step 4: Second Stage Association (Detections Low with Remaining Active Tracks)
        unmatched_active_ids = [t_id for t_id in active_track_ids if t_id not in matched_tracks]
        if unmatched_active_ids and dets_low_idx:
            matches_stage2 = []
            for d_idx in dets_low_idx:
                det = detections[d_idx]
                for t_id in unmatched_active_ids:
                    track = self.tracks[t_id]
                    pred_box = track.to_detection_box()
                    iou = calculate_iou_boxes(pred_box, det)
                    if iou >= self.match_thresh:
                        matches_stage2.append((iou, d_idx, t_id))

            matches_stage2.sort(key=lambda x: -x[0])
            for iou, d_idx, t_id in matches_stage2:
                if d_idx not in matched_dets and t_id not in matched_tracks:
                    matched_dets.add(d_idx)
                    matched_tracks.add(t_id)

                    speed = self.speed_estimator.estimate_speed(t_id, detections[d_idx], frame_idx, fps)
                    self.tracks[t_id].update(detections[d_idx], frame_idx=frame_idx, speed_kmh=speed)

                    detections[d_idx].track_id = t_id
                    detections[d_idx].speed_kmh = speed
                    detections[d_idx].trajectory = list(self.tracks[t_id].trajectory)
                    output_detections.append(detections[d_idx])

        # Step 5: Recovery Association (Remaining Unmatched Detections High with Lost Tracks)
        unmatched_high_idx = [d_idx for d_idx in dets_high_idx if d_idx not in matched_dets]
        if unmatched_high_idx and lost_track_ids:
            matches_recovery = []
            for d_idx in unmatched_high_idx:
                det = detections[d_idx]
                for t_id in lost_track_ids:
                    track = self.tracks[t_id]
                    pred_box = track.to_detection_box()
                    iou = calculate_iou_boxes(pred_box, det)
                    if iou >= self.recovery_thresh:
                        matches_recovery.append((iou, d_idx, t_id))

            matches_recovery.sort(key=lambda x: -x[0])
            for iou, d_idx, t_id in matches_recovery:
                if d_idx not in matched_dets and t_id not in matched_tracks:
                    matched_dets.add(d_idx)
                    matched_tracks.add(t_id)
                    self.lost_tracks_recovered += 1

                    speed = self.speed_estimator.estimate_speed(t_id, detections[d_idx], frame_idx, fps)
                    self.tracks[t_id].update(detections[d_idx], frame_idx=frame_idx, speed_kmh=speed)

                    detections[d_idx].track_id = t_id
                    detections[d_idx].speed_kmh = speed
                    detections[d_idx].trajectory = list(self.tracks[t_id].trajectory)
                    output_detections.append(detections[d_idx])

        # Step 6: Initialize New Tracks ONLY for unmatched HIGH-confidence detections
        newly_created_ids = set()
        for d_idx in dets_high_idx:
            if d_idx not in matched_dets:
                det = detections[d_idx]
                new_id = self._next_id
                self._next_id += 1
                self.total_tracks_created += 1

                det.track_id = new_id
                speed = self.speed_estimator.estimate_speed(new_id, det, frame_idx, fps)
                det.speed_kmh = speed

                new_track = ByteTracklet(new_id, det, frame_idx=frame_idx)
                new_track.speed_kmh = speed
                self.tracks[new_id] = new_track
                det.trajectory = list(new_track.trajectory)
                output_detections.append(det)
                newly_created_ids.add(new_id)

        # Step 7: Mark unmatched tracks as LOST and prune dead tracks exceeding max_lost_frames
        dead_tracks = []
        for t_id, track in self.tracks.items():
            if t_id not in matched_tracks and t_id not in newly_created_ids:
                track.mark_lost()
                if track.lost_frames > self.max_lost_frames:
                    dead_tracks.append(t_id)

        for t_id in dead_tracks:
            del self.tracks[t_id]

        return output_detections

    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns tracker health, association metrics, and recovery statistics."""
        active = sum(1 for t in self.tracks.values() if t.state == TrackState.TRACKED)
        lost = sum(1 for t in self.tracks.values() if t.state == TrackState.LOST)
        confirmed = sum(1 for t in self.tracks.values() if t.is_confirmed)
        return {
            "tracker_type": "ByteTrackVehicleTracker",
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

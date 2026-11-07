"""
traffic_system/computer_vision/tracker.py - Multi-Object Vehicle Tracker
High-performance vehicle tracking powered by ByteTrack and an 8-state linear Kalman Filter.
Assigns persistent unique track IDs, models velocity, bridges momentary occlusions,
and eliminates duplicate counting during stop-and-go congestion.
"""

from typing import List, Dict, Any, Optional
from traffic_system.computer_vision.schemas import DetectionBox
from traffic_system.computer_vision.speed_estimator import SpeedEstimator
from traffic_system.computer_vision.bytetrack import (
    ByteTrackVehicleTracker,
    ByteTracklet,
    TrackState,
    calculate_iou_boxes
)

# Export aliases for full backward compatibility
calculate_iou = calculate_iou_boxes
Tracklet = ByteTracklet


class VehicleTracker(ByteTrackVehicleTracker):
    """
    ByteTrack-powered multi-object vehicle tracker.
    Associates high- and low-confidence detections via an 8-state Kalman Filter to
    prevent ID switches and track loss during stop-and-go traffic and occlusions.
    """
    def __init__(
        self,
        iou_threshold: float = 0.25,
        recovery_iou_threshold: float = 0.15,
        max_lost_frames: int = 90,
        min_hits_to_confirm: int = 2,
        speed_estimator: Optional[SpeedEstimator] = None,
        high_conf_thresh: float = 0.30,
        low_conf_thresh: float = 0.10
    ):
        super().__init__(
            high_conf_thresh=high_conf_thresh,
            low_conf_thresh=low_conf_thresh,
            match_thresh=iou_threshold,
            recovery_thresh=recovery_iou_threshold,
            max_lost_frames=max_lost_frames,
            min_hits_to_confirm=min_hits_to_confirm,
            speed_estimator=speed_estimator
        )
        self.iou_threshold = iou_threshold
        self.recovery_iou_threshold = recovery_iou_threshold

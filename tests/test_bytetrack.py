"""
tests/test_bytetrack.py - Unit Tests for Kalman Filter & ByteTrack Association Engine
Verifies:
1. Kalman filter bounding box state propagation and velocity estimation.
2. Two-stage ByteTrack association matching both high- and low-confidence detections.
3. Occlusion recovery preserving persistent Track ID across 10+ dropped frames.
4. Spurious low-confidence detection rejection from spawning ghost tracks.
"""

import pytest
import numpy as np
from traffic_system.computer_vision.schemas import DetectionBox
from traffic_system.computer_vision.kalman_filter import KalmanBoxFilter
from traffic_system.computer_vision.bytetrack import ByteTrackVehicleTracker, ByteTracklet


def test_kalman_box_filter_predict_and_update():
    """Verify 8-state Kalman Filter updates position and estimates velocity."""
    kf = KalmanBoxFilter()
    # Initial box: [x1, y1, x2, y2] = [100, 100, 160, 200] -> center=(130, 150), a=0.6, h=100
    init_box = np.array([100.0, 100.0, 160.0, 200.0])
    mean, cov = kf.initiate(init_box)

    assert mean.shape == (8,)
    assert abs(mean[0] - 130.0) < 1e-3
    assert abs(mean[1] - 150.0) < 1e-3
    assert abs(mean[3] - 100.0) < 1e-3

    # Predict next state
    mean_pred, cov_pred = kf.predict(mean, cov)
    assert mean_pred.shape == (8,)

    # Update with shifted measurement [105, 100, 165, 200] (moved dx=+5)
    new_box = np.array([105.0, 100.0, 165.0, 200.0])
    mean_upd, cov_upd = kf.update(mean_pred, cov_pred, new_box)

    # Velocity vx (mean[4]) should now be positive
    assert mean_upd[4] > 0.0


def test_bytetrack_low_confidence_recovery():
    """Verify low-confidence detection matches existing track rather than getting discarded."""
    tracker = ByteTrackVehicleTracker(high_conf_thresh=0.50, low_conf_thresh=0.15)

    # Frame 1: Vehicle detected with high confidence (0.85)
    f1_det = [
        DetectionBox(x1=100, y1=100, x2=200, y2=200, confidence=0.85, class_id=2, class_name="car")
    ]
    tracked_f1 = tracker.update(f1_det, frame_idx=1)
    assert len(tracked_f1) == 1
    track_id = tracked_f1[0].track_id
    assert track_id is not None

    # Frame 2: Vehicle partially occluded or in shadow (confidence drops to 0.25)
    # ByteTrack must associate it to the existing track_id rather than dropping it
    f2_det = [
        DetectionBox(x1=104, y1=102, x2=204, y2=202, confidence=0.25, class_id=2, class_name="car")
    ]
    tracked_f2 = tracker.update(f2_det, frame_idx=2)
    assert len(tracked_f2) == 1
    assert tracked_f2[0].track_id == track_id, "ByteTrack must preserve ID through low confidence"


def test_bytetrack_ghost_track_rejection():
    """Verify that isolated low-confidence detections NEVER create new tracks."""
    tracker = ByteTrackVehicleTracker(high_conf_thresh=0.50, low_conf_thresh=0.15)

    # Isolated low confidence detection (0.20) without prior track
    dets = [
        DetectionBox(x1=50, y1=50, x2=90, y2=90, confidence=0.20, class_id=2, class_name="car")
    ]
    tracked = tracker.update(dets, frame_idx=1)
    # Should not spawn a new track
    assert len(tracked) == 0
    assert tracker.total_tracks_created == 0


def test_bytetrack_occlusion_recovery_across_frames():
    """Verify vehicle preserves Track ID after 10 frames of complete occlusion."""
    tracker = ByteTrackVehicleTracker(max_lost_frames=30)

    # Frame 1 to 3: Establish confirmed track
    for f in range(1, 4):
        dets = [
            DetectionBox(x1=100 + f * 5, y1=200, x2=160 + f * 5, y2=280, confidence=0.90, class_id=2, class_name="car")
        ]
        t = tracker.update(dets, frame_idx=f)
        orig_id = t[0].track_id

    # Frames 4 to 14: Occlusion (zero detections)
    for f in range(4, 15):
        tracker.update([], frame_idx=f)

    # Frame 15: Vehicle re-emerges near predicted location
    reemerge_dets = [
        DetectionBox(x1=100 + 15 * 5, y1=200, x2=160 + 15 * 5, y2=280, confidence=0.88, class_id=2, class_name="car")
    ]
    res = tracker.update(reemerge_dets, frame_idx=15)
    assert len(res) == 1
    assert res[0].track_id == orig_id, f"Expected Track ID {orig_id} to be recovered, got {res[0].track_id}"

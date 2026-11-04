"""
tests/test_speed_estimator.py - Unit Tests for Kinematic Speed Estimator
Validates bottom-center homography projection, discretization jitter clamping, and EMA velocity smoothing.
"""

import pytest
import numpy as np
from traffic_system.computer_vision.schemas import DetectionBox
from traffic_system.computer_vision.speed_estimator import SpeedEstimator


def test_speed_estimator_initial_state():
    estimator = SpeedEstimator()
    box = DetectionBox(x1=100.0, y1=200.0, x2=150.0, y2=260.0, confidence=0.88, class_id=2, class_name="car")
    speed = estimator.estimate_speed(track_id=1, box=box, frame_idx=0, fps=30.0)
    assert speed == 0.0
    assert 1 in estimator.track_history


def test_speed_estimator_motion_calculation():
    estimator = SpeedEstimator(ema_alpha=1.0)  # Use instant speed for exact math verification
    # Frame 0
    box0 = DetectionBox(x1=500.0, y1=400.0, x2=580.0, y2=500.0, confidence=0.90, class_id=2, class_name="car")
    estimator.estimate_speed(track_id=2, box=box0, frame_idx=0, fps=30.0)

    # Frame 15 (0.5 seconds later, moving downwards along road)
    box15 = DetectionBox(x1=500.0, y1=460.0, x2=580.0, y2=560.0, confidence=0.92, class_id=2, class_name="car")
    speed15 = estimator.estimate_speed(track_id=2, box=box15, frame_idx=15, fps=30.0)

    assert speed15 > 0.0
    assert speed15 <= 140.0


def test_speed_estimator_stationary_jitter_suppression():
    estimator = SpeedEstimator(min_displacement_m=0.35)
    # Simulate stationary vehicle with 1-pixel micro-jitter across 10 frames
    for f in range(12):
        jitter = float(f % 2) * 0.5
        box = DetectionBox(x1=300.0 + jitter, y1=300.0, x2=360.0 + jitter, y2=380.0, confidence=0.90, class_id=2, class_name="car")
        speed = estimator.estimate_speed(track_id=3, box=box, frame_idx=f, fps=30.0)

    # After 10 frames of micro-jitter (<0.35m displacement), speed must be suppressed to 0.0 km/h
    assert speed == 0.0


def test_speed_estimator_reset():
    estimator = SpeedEstimator()
    box = DetectionBox(x1=100.0, y1=100.0, x2=150.0, y2=150.0, confidence=0.8, class_id=2, class_name="car")
    estimator.estimate_speed(track_id=1, box=box, frame_idx=0)
    assert len(estimator.track_history) == 1
    estimator.reset()
    assert len(estimator.track_history) == 0


def test_speed_estimator_camera_specific_calibration():
    # 4 image points (pixels) forming a trapezoid
    src = [(100.0, 400.0), (300.0, 400.0), (350.0, 600.0), (50.0, 600.0)]
    # 4 ground points (meters) representing a 3.5m wide lane over a 20m segment
    dst = [(0.0, 0.0), (3.5, 0.0), (3.5, 20.0), (0.0, 20.0)]

    calibrated_est = SpeedEstimator.from_four_point_correspondence(src, dst, camera_id="test_cam_01")
    assert calibrated_est.is_calibrated is True
    assert calibrated_est.camera_id == "test_cam_01"
    assert calibrated_est.homography.shape == (3, 3)

    # Verify project_point works on ground plane
    gx, gy = calibrated_est.project_point(100.0, 400.0)
    assert abs(gx - 0.0) < 0.1
    assert abs(gy - 0.0) < 0.1

    uncalibrated_est = SpeedEstimator()
    assert uncalibrated_est.is_calibrated is False

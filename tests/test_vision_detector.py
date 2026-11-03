"""
tests/test_vision_detector.py - Unit Tests for Vehicle Detection Module
"""

import numpy as np
from traffic_system.computer_vision.detector import VehicleDetector
from traffic_system.computer_vision.schemas import DetectionBox


def test_detector_initialization():
    detector = VehicleDetector(conf_threshold=0.35)
    assert detector.conf_threshold == 0.35
    assert hasattr(detector, "detect_frame")


def test_detector_frame_inference():
    detector = VehicleDetector(conf_threshold=0.30)
    fake_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    detections = detector.detect_frame(fake_frame, frame_idx=1)
    assert isinstance(detections, list)
    assert len(detections) > 0

    valid_classes = {"car", "motorcycle", "bus", "truck"}
    for det in detections:
        assert isinstance(det, DetectionBox)
        assert det.class_name.lower() in valid_classes
        assert det.confidence >= 0.30
        assert 0.0 <= det.x1 <= det.x2 <= 1280.0
        assert 0.0 <= det.y1 <= det.y2 <= 720.0


def test_detector_confidence_threshold_filtering():
    detector = VehicleDetector(conf_threshold=0.90)
    fake_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    detections = detector.detect_frame(fake_frame, conf_threshold=0.90, frame_idx=5)
    for det in detections:
        assert det.confidence >= 0.90

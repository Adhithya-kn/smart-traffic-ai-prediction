"""
tests/test_vision_detector.py - Unit Tests for Vehicle Detection Module
Enforces genuine YOLO model inference and zero synthetic fallbacks on blank frames.
"""

from pathlib import Path
import cv2
import numpy as np
import pytest
from traffic_system.computer_vision.detector import (
    VehicleDetector,
    YOLOUnavailableError,
    YOLOInferenceError
)
from traffic_system.computer_vision.schemas import DetectionBox


def test_detector_initialization():
    detector = VehicleDetector(conf_threshold=0.35)
    assert detector.conf_threshold == 0.35
    assert hasattr(detector, "detect_frame")
    assert detector.is_yolo_active is True


def test_detector_zero_detections_on_blank_frame():
    """If YOLO detects zero vehicles on a blank frame, it MUST return an empty list."""
    detector = VehicleDetector(conf_threshold=0.30)
    blank_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    detections = detector.detect_frame(blank_frame, frame_idx=1)
    assert isinstance(detections, list)
    assert len(detections) == 0, f"Expected 0 detections on blank frame, got {len(detections)}"


def test_detector_real_frame_inference():
    """Genuine YOLO inference on a real sample traffic video frame."""
    detector = VehicleDetector(conf_threshold=0.25)
    sample_video_path = Path("app/static/sample_traffic.mp4")
    assert sample_video_path.exists(), "Sample video file must exist for genuine inference testing."

    cap = cv2.VideoCapture(str(sample_video_path))
    assert cap.isOpened(), "Failed to open sample video with OpenCV."
    ret, frame = cap.read()
    cap.release()
    assert ret and frame is not None

    detections = detector.detect_frame(frame, frame_idx=0)
    assert isinstance(detections, list)
    assert len(detections) > 0, "Expected genuine detections on real traffic frame."

    valid_classes = {"car", "motorcycle", "bus", "truck", "pedestrian", "bicycle"}
    for det in detections:
        assert isinstance(det, DetectionBox)
        assert det.class_name.lower() in valid_classes
        assert det.confidence >= 0.25
        assert 0.0 <= det.x1 <= det.x2 <= frame.shape[1]
        assert 0.0 <= det.y1 <= det.y2 <= frame.shape[0]


def test_detector_confidence_threshold_filtering():
    """Higher threshold filters out lower-confidence genuine detections."""
    detector = VehicleDetector(conf_threshold=0.85)
    sample_video_path = Path("app/static/sample_traffic.mp4")
    cap = cv2.VideoCapture(str(sample_video_path))
    ret, frame = cap.read()
    cap.release()
    assert ret and frame is not None

    detections = detector.detect_frame(frame, conf_threshold=0.85, frame_idx=0)
    for det in detections:
        assert det.confidence >= 0.85


def test_detector_unavailable_yolo_raises_error():
    """If YOLO is unavailable, detect_frame must raise YOLOUnavailableError."""
    detector = VehicleDetector()
    detector._is_yolo_loaded = False
    detector.model = None
    detector.load_error = "Mock weights failure"

    blank_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    with pytest.raises(YOLOUnavailableError) as exc_info:
        detector.detect_frame(blank_frame)
    assert "Mock weights failure" in str(exc_info.value)

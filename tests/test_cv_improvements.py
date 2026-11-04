"""
tests/test_cv_improvements.py - Validation for Vehicle Detection, Classification and Tracking Improvements
Verifies:
1. COCO class mapping (bicycles separated from motorcycles, pedestrians excluded).
2. Configurable detector parameters and device metadata recording.
3. Vehicle counter unknown-class handling (no car fallback) and bicycle support.
4. Separation of current-frame counts vs cumulative unique counts.
5. Tracker class consistency and occlusion recovery without duplicate track IDs.
6. Indo-HCM PCU conversion for bicycles and auto-rickshaws.
7. End-to-end sample video processing and result verification.
"""

import os
from pathlib import Path
import pytest
import numpy as np

from traffic_system.computer_vision.detector import (
    VehicleDetector,
    COCO_VEHICLE_MAP,
    COCO_NON_VEHICLE_MAP,
    COCO_ALL_CLASSES
)
from traffic_system.computer_vision.schemas import DetectionBox, VEHICLE_CLASSES
from traffic_system.computer_vision.vehicle_counter import VehicleCounter, CANONICAL_VEHICLE_CLASSES
from traffic_system.computer_vision.tracker import VehicleTracker, TrackState
from traffic_system.computer_vision.pcu_converter import IndoHCMPCUConverter, INDO_HCM_PCU_FACTORS
from traffic_system.computer_vision.video_processor import VideoProcessor
from traffic_system.config import BASE_DIR


def test_coco_class_mapping_and_pedestrian_exclusion():
    """Verify COCO mappings separate motorcycles from bicycles and exclude pedestrians from vehicles."""
    assert 1 in COCO_VEHICLE_MAP
    assert COCO_VEHICLE_MAP[1] == "bicycle"

    assert 2 in COCO_VEHICLE_MAP
    assert COCO_VEHICLE_MAP[2] == "car"

    assert 3 in COCO_VEHICLE_MAP
    assert COCO_VEHICLE_MAP[3] == "motorcycle"

    # Distinct classes
    assert COCO_VEHICLE_MAP[1] != COCO_VEHICLE_MAP[3]

    # Pedestrians must NOT be in vehicle map
    assert 0 not in COCO_VEHICLE_MAP
    assert 0 in COCO_NON_VEHICLE_MAP
    assert COCO_NON_VEHICLE_MAP[0] == "pedestrian"

    # Supported schemas must include bicycle
    assert "bicycle" in VEHICLE_CLASSES
    assert VEHICLE_CLASSES["bicycle"] == "Bicycle"


def test_detector_configurable_params_and_device_recording():
    """Verify detector resolution, confidence, and inference device are configurable and recorded."""
    detector = VehicleDetector(
        conf_threshold=0.35,
        imgsz=512,
        device="cpu"
    )
    assert detector.conf_threshold == 0.35
    assert detector.imgsz == 512
    assert detector.actual_device == "cpu"

    info = detector.get_device_info()
    assert info["conf_threshold"] == 0.35
    assert info["imgsz"] == 512
    assert info["device"] == "cpu"
    assert "yolo" in info["model_name"].lower()


def test_vehicle_counter_bicycle_and_unknown_rejection():
    """Verify bicycle is tracked separately and unknown objects do NOT fall back to cars."""
    counter = VehicleCounter(min_hits=1)

    # Frame with valid and invalid detections
    dets = [
        DetectionBox(x1=10, y1=10, x2=50, y2=50, confidence=0.85, class_id=2, class_name="car", track_id=1),
        DetectionBox(x1=60, y1=10, x2=80, y2=40, confidence=0.90, class_id=1, class_name="bicycle", track_id=2),
        DetectionBox(x1=90, y1=10, x2=110, y2=40, confidence=0.88, class_id=3, class_name="motorcycle", track_id=3),
        DetectionBox(x1=120, y1=10, x2=140, y2=60, confidence=0.92, class_id=0, class_name="pedestrian", track_id=4),
        DetectionBox(x1=150, y1=10, x2=170, y2=60, confidence=0.75, class_id=99, class_name="unknown_traffic_cone", track_id=5),
    ]

    res = counter.update(dets)

    # Car count must be strictly 1, NOT incremented by pedestrian or unknown object
    assert res["current_frame_classes"]["car"] == 1
    assert res["current_frame_classes"]["bicycle"] == 1
    assert res["current_frame_classes"]["motorcycle"] == 1
    assert res["current_frame_total"] == 3  # car + bicycle + motorcycle only

    summary = counter.get_summary()
    assert summary["class_counts"]["car"] == 1
    assert summary["class_counts"]["bicycle"] == 1
    assert summary["class_counts"]["motorcycle"] == 1
    assert summary["total_unique_vehicles"] == 3


def test_vehicle_counter_current_vs_cumulative_separation():
    """Verify current-frame counts are kept strictly separate from cumulative unique vehicle totals."""
    counter = VehicleCounter(min_hits=1)

    # Frame 1: Tracks 1, 2, 3 appear
    f1 = [
        DetectionBox(x1=10, y1=10, x2=50, y2=50, confidence=0.85, class_id=2, class_name="car", track_id=1),
        DetectionBox(x1=60, y1=10, x2=100, y2=50, confidence=0.85, class_id=2, class_name="car", track_id=2),
        DetectionBox(x1=110, y1=10, x2=150, y2=50, confidence=0.85, class_id=5, class_name="bus", track_id=3),
    ]
    r1 = counter.update(f1)
    assert r1["current_frame_total"] == 3
    assert r1["cumulative_unique_total"] == 3

    # Frame 2: Track 1 continues, Track 2 leaves, Track 3 continues, Track 4 (new truck) enters
    f2 = [
        DetectionBox(x1=15, y1=15, x2=55, y2=55, confidence=0.88, class_id=2, class_name="car", track_id=1),
        DetectionBox(x1=115, y1=15, x2=155, y2=55, confidence=0.88, class_id=5, class_name="bus", track_id=3),
        DetectionBox(x1=200, y1=10, x2=280, y2=80, confidence=0.91, class_id=7, class_name="truck", track_id=4),
    ]
    r2 = counter.update(f2)

    # Current frame should be 3
    assert r2["current_frame_total"] == 3
    # Cumulative unique vehicles should be 4 (tracks 1, 2, 3, 4)
    assert r2["cumulative_unique_total"] == 4
    assert r2["cumulative_classes"]["car"] == 2
    assert r2["cumulative_classes"]["bus"] == 1
    assert r2["cumulative_classes"]["truck"] == 1


def test_tracker_class_consistency_and_occlusion_recovery():
    """Verify tracklet preserves original class label and recovers temporarily occluded vehicle."""
    tracker = VehicleTracker(iou_threshold=0.25, recovery_iou_threshold=0.15, max_lost_frames=5)

    # Frame 0: Car detected at (100, 100, 150, 150)
    d0 = [DetectionBox(x1=100, y1=100, x2=150, y2=150, confidence=0.9, class_id=2, class_name="car")]
    t0 = tracker.update(d0, frame_idx=0)
    assigned_id = t0[0].track_id
    assert assigned_id is not None
    assert t0[0].class_name == "car"

    # Frame 1: Vehicle moves to (110, 110, 160, 160)
    d1 = [DetectionBox(x1=110, y1=110, x2=160, y2=160, confidence=0.9, class_id=2, class_name="car")]
    t1 = tracker.update(d1, frame_idx=1)
    assert t1[0].track_id == assigned_id

    # Frame 2: Vehicle is occluded / disappears (zero detections in frame)
    t2 = tracker.update([], frame_idx=2)
    assert tracker.tracks[assigned_id].state == TrackState.LOST
    assert tracker.tracks[assigned_id].lost_frames == 1

    # Frame 3: Vehicle re-emerges near projected location (130, 130, 180, 180)
    d3 = [DetectionBox(x1=130, y1=130, x2=180, y2=180, confidence=0.88, class_id=2, class_name="car")]
    t3 = tracker.update(d3, frame_idx=3)

    # Must recover the SAME assigned_id (no duplicate ID created)
    assert t3[0].track_id == assigned_id
    assert tracker.lost_tracks_recovered >= 1
    assert tracker.tracks[assigned_id].state == TrackState.TRACKED


def test_pcu_converter_bicycle_and_no_auto_rickshaw_reclassification():
    """Verify PCU factors for bicycle and strict isolation of unsupported auto-rickshaws."""
    assert "bicycle" in INDO_HCM_PCU_FACTORS
    assert INDO_HCM_PCU_FACTORS["bicycle"] == 0.20

    # Auto-rickshaw factor is 0.80
    assert INDO_HCM_PCU_FACTORS["auto_rickshaw"] == 0.80

    # Counts dictionary
    counts = {
        "car": 10,       # 10 * 1.00 = 10.0
        "motorcycle": 8,  # 8 * 0.50 = 4.0
        "bicycle": 5,     # 5 * 0.20 = 1.0
        "bus": 2,         # 2 * 2.80 = 5.6
        "truck": 1        # 1 * 3.00 = 3.0
    }
    total_pcu = IndoHCMPCUConverter.calculate_total_pcu(counts)
    expected = 10.0 + 4.0 + 1.0 + 5.6 + 3.0  # 23.6
    assert abs(total_pcu - expected) < 1e-3

    # Extrapolated hourly flow disclaimer
    telemetry = IndoHCMPCUConverter.get_flow_telemetry(total_pcu, 30.0)
    assert telemetry["is_actual_measured_hourly_flow"] is False
    assert "extrapolated" in telemetry["flow_rate_type"]


def test_sample_video_genuine_processing_lifecycle(tmp_path):
    """Verify sample video runs through genuine YOLO processing pipeline with complete telemetry output."""
    sample_mp4 = BASE_DIR / "app" / "static" / "sample_traffic.mp4"
    assert sample_mp4.exists(), f"Sample traffic video missing at {sample_mp4}"

    out_mp4 = tmp_path / "processed_test.mp4"
    processor = VideoProcessor(
        max_frames=15,  # Process 15 frames for fast unit testing
        frame_stride=2,
        simulation_mode=False
    )

    result = processor.process_video(
        input_path=sample_mp4,
        output_path=out_mp4
    )

    # Verify output video file created and verified
    assert out_mp4.exists()
    assert out_mp4.stat().st_size > 0

    # Verify result structure and provenance
    assert result["processing_provenance"] == "GENUINE_YOLO_INFERENCE"
    assert result["is_simulation"] is False
    assert "confidence_summary" in result
    assert result["confidence_summary"]["detection_threshold"] == processor.conf_threshold
    assert "class_counts" in result

    # Check vehicle classes in class_counts
    for c in ["car", "motorcycle", "bicycle", "bus", "truck"]:
        assert c in result["class_counts"]

    # Verify telemetry frames contain class-wise breakdowns
    assert len(result["sample_telemetry"]) > 0
    first_frame = result["sample_telemetry"][0]
    assert "current_frame_classes" in first_frame
    assert "cumulative_classes" in first_frame
    assert "cumulative_unique_total" in first_frame

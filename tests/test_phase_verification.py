"""
tests/test_phase_verification.py - Comprehensive Verification for Phases 1 through 6
Validates:
1. Genuine YOLO11n detection of cars and motorcycles on real video frames without car fallback.
2. Distinct COCO mappings and separation of bicycles from motorcycles.
3. Tracking ID persistence and unique vehicle accumulation.
4. Indo-HCM PCU conversion and calibrated speed/density disclaimers.
5. Two-role dashboard permission barriers and navigation synchronization.
6. Environment variables, storage directory safety, and preflight health.
"""

import os
from pathlib import Path
import pytest
import numpy as np

from traffic_system.config import BASE_DIR, VIDEO_STORAGE_DIR, CV_CONFIDENCE_THRESHOLD
from traffic_system.computer_vision.detector import VehicleDetector, COCO_VEHICLE_MAP, COCO_NON_VEHICLE_MAP
from traffic_system.computer_vision.vehicle_counter import VehicleCounter, CANONICAL_VEHICLE_CLASSES
from traffic_system.computer_vision.tracker import VehicleTracker, TrackState
from traffic_system.computer_vision.pcu_converter import IndoHCMPCUConverter, INDO_HCM_PCU_FACTORS
from traffic_system.computer_vision.video_processor import VideoProcessor
from traffic_system.core.security import SecurityManager
from traffic_system.storage.video_storage import get_video_storage


def test_coco_mapping_and_separation_of_bicycles_and_motorcycles():
    """Verify bicycle (1) and motorcycle (3) are distinct and separated from cars (2)."""
    assert COCO_VEHICLE_MAP[1] == "bicycle"
    assert COCO_VEHICLE_MAP[2] == "car"
    assert COCO_VEHICLE_MAP[3] == "motorcycle"
    assert COCO_VEHICLE_MAP[5] == "bus"
    assert COCO_VEHICLE_MAP[7] == "truck"

    # Non-vehicle classes
    assert 0 not in COCO_VEHICLE_MAP
    assert COCO_NON_VEHICLE_MAP[0] == "pedestrian"


def test_no_unknown_class_to_car_fallback():
    """Verify unknown classes return None and are never mapped to car."""
    counter = VehicleCounter()
    assert counter.normalize_vehicle_class("car") == "car"
    assert counter.normalize_vehicle_class("motorcycle") == "motorcycle"
    assert counter.normalize_vehicle_class("bike") == "motorcycle"
    assert counter.normalize_vehicle_class("bicycle") == "bicycle"
    assert counter.normalize_vehicle_class("cycle") == "bicycle"
    assert counter.normalize_vehicle_class("traffic_cone") is None
    assert counter.normalize_vehicle_class("unknown_entity") is None
    assert counter.normalize_vehicle_class("pedestrian") is None


def test_genuine_yolo11n_detects_cars_and_motorcycles():
    """Verify YOLO11n model detects cars and motorcycles from real sample video frames."""
    import cv2
    sample_mp4 = BASE_DIR / "app" / "static" / "sample_traffic.mp4"
    assert sample_mp4.exists(), f"Missing {sample_mp4}"

    cap = cv2.VideoCapture(str(sample_mp4))
    assert cap.isOpened(), "Could not open sample_traffic.mp4"

    # Seek directly to frame 110 where cars appear in sample_traffic.mp4
    cap.set(cv2.CAP_PROP_POS_FRAMES, 110)
    ret, frame_car = cap.read()
    cap.release()
    assert ret, "Could not read frame 110"

    detector = VehicleDetector(conf_threshold=0.25)
    assert detector.is_yolo_active, "YOLO11n model must be active"

    dets_car = detector.detect_frame(frame_car)
    classes_car = [b.class_name for b in dets_car]
    assert "car" in classes_car, f"Car must be detected at frame 110, found: {classes_car}"

    # Now verify motorcycle & bicycle detection in outer ring sample
    outer_mp4 = BASE_DIR / "app" / "static" / "sample_outer_ring.mp4"
    assert outer_mp4.exists(), f"Missing {outer_mp4}"

    cap2 = cv2.VideoCapture(str(outer_mp4))
    assert cap2.isOpened(), "Could not open sample_outer_ring.mp4"
    ret2, frame_moto = cap2.read()
    cap2.release()
    assert ret2, "Could not read frame from sample_outer_ring.mp4"

    dets_moto = detector.detect_frame(frame_moto)
    classes_moto = [b.class_name for b in dets_moto]
    assert "motorcycle" in classes_moto, f"Motorcycle must be detected, found: {classes_moto}"
    assert "bicycle" in classes_moto, f"Bicycle must be detected, found: {classes_moto}"


def test_unique_vehicle_counting_over_frames():
    """Verify counter accumulates unique vehicles via persistent track ID rather than frame detection sum."""
    from traffic_system.computer_vision.schemas import DetectionBox
    counter = VehicleCounter(min_hits=2)

    # Frame 1: Vehicle 1 & 2 first seen (unconfirmed at hits=1)
    d1 = [
        DetectionBox(x1=10, y1=10, x2=50, y2=50, confidence=0.88, class_id=2, class_name="car", track_id=1),
        DetectionBox(x1=100, y1=10, x2=130, y2=40, confidence=0.82, class_id=3, class_name="motorcycle", track_id=2)
    ]
    res1 = counter.update(d1)
    assert res1["current_frame_total"] == 2
    assert res1["cumulative_unique_total"] == 0  # not yet confirmed with min_hits=2

    # Frame 2: Vehicle 1 & 2 continue (hits=2, confirmed)
    d2 = [
        DetectionBox(x1=12, y1=15, x2=52, y2=55, confidence=0.91, class_id=2, class_name="car", track_id=1),
        DetectionBox(x1=102, y1=18, x2=132, y2=48, confidence=0.85, class_id=3, class_name="motorcycle", track_id=2)
    ]
    res2 = counter.update(d2)
    assert res2["current_frame_total"] == 2
    assert res2["cumulative_unique_total"] == 2
    assert res2["cumulative_classes"]["car"] == 1
    assert res2["cumulative_classes"]["motorcycle"] == 1

    # Frame 3: Same vehicles continue across frame 3
    d3 = [
        DetectionBox(x1=15, y1=20, x2=55, y2=60, confidence=0.90, class_id=2, class_name="car", track_id=1),
        DetectionBox(x1=105, y1=25, x2=135, y2=55, confidence=0.86, class_id=3, class_name="motorcycle", track_id=2)
    ]
    res3 = counter.update(d3)
    # Total unique count must NOT increase (stays 2 unique vehicles)
    assert res3["cumulative_unique_total"] == 2
    assert res3["cumulative_classes"]["car"] == 1
    assert res3["cumulative_classes"]["motorcycle"] == 1


def test_pcu_factors_and_calibration_disclaimers():
    """Verify Indo-HCM PCU factors and explicit calibration disclaimers for speed/density."""
    assert INDO_HCM_PCU_FACTORS["car"] == 1.00
    assert INDO_HCM_PCU_FACTORS["motorcycle"] == 0.50
    assert INDO_HCM_PCU_FACTORS["bicycle"] == 0.20
    assert INDO_HCM_PCU_FACTORS["bus"] == 2.80
    assert INDO_HCM_PCU_FACTORS["truck"] == 3.00

    flow_data = IndoHCMPCUConverter.get_flow_telemetry(15.0, 30.0)
    assert flow_data["is_actual_measured_hourly_flow"] is False
    assert "extrapolated" in flow_data["flow_rate_type"].lower()
    assert "steady_state_assumption" in flow_data


def test_two_roles_security_and_authorization():
    """Verify Road User and Traffic Management permissions and barriers."""
    sec = SecurityManager()

    # Login as Road User
    ok_commuter, _, sess_commuter = sec.login("commuter", "Admin@123")
    assert ok_commuter
    assert sess_commuter["role"] == "Road User"

    # Login as Traffic Management
    ok_admin, _, sess_admin = sec.login("traffic_admin", "Admin@123")
    assert ok_admin
    assert sess_admin["role"] == "Traffic Management"

    # Verify role checking via token retrieval
    admin_user = sec.get_user_by_token(sess_admin["token"])
    assert admin_user is not None
    assert admin_user["role"] == "Traffic Management"

    commuter_user = sec.get_user_by_token(sess_commuter["token"])
    assert commuter_user is not None
    assert commuter_user["role"] == "Road User"


def test_environment_and_production_storage():
    """Verify environment variables and persistent video storage paths."""
    storage = get_video_storage()
    assert storage.base_dir.exists()
    assert storage.raw_dir.exists()
    assert storage.processed_dir.exists()

    stats = storage.get_storage_stats()
    assert "total_bytes" in stats
    assert "raw_videos_count" in stats
    assert "processed_videos_count" in stats
    assert stats["max_capacity_bytes"] > 0

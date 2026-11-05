"""
tests/test_pedestrian_crowd_and_incident_filter.py - Tests for Pedestrian Noise Exclusion and Crowd Telemetry
Ensures:
1. Pedestrians never trigger false vehicle deceleration or wrong-way alarms.
2. Vehicle deceleration is clamped to physical maximums.
3. Pedestrian detections are accumulated into crowd density and Fruin LOS metrics.
"""

import pytest
from traffic_system.computer_vision.incident_detector import IncidentDetector
from traffic_system.computer_vision.vehicle_counter import VehicleCounter
from traffic_system.computer_vision.schemas import DetectionBox


def test_pedestrians_excluded_from_deceleration_and_wrong_way_incidents():
    detector = IncidentDetector()
    ped_box = DetectionBox(x1=10, y1=10, x2=20, y2=40, confidence=0.85, class_id=0, class_name="pedestrian")

    # Simulate pedestrian track moving and then stopping abruptly (common walking jitter)
    detector.update(track_id=1, box=ped_box, speed_kmh=25.0, frame_idx=0, fps=30.0)
    incidents = detector.update(track_id=1, box=ped_box, speed_kmh=0.0, frame_idx=1, fps=30.0)

    # MUST NOT generate deceleration incident for pedestrian
    assert len(incidents) == 0


def test_vehicle_deceleration_clamped_to_physical_limits():
    detector = IncidentDetector()
    car_box = DetectionBox(x1=10, y1=10, x2=50, y2=50, confidence=0.9, class_id=2, class_name="car")

    # 60 km/h to 0 in 1 frame (impossible -350 m/s^2 without physical crash)
    detector.update(track_id=2, box=car_box, speed_kmh=60.0, frame_idx=0, fps=30.0)
    incidents = detector.update(track_id=2, box=car_box, speed_kmh=0.0, frame_idx=1, fps=30.0)

    assert len(incidents) == 1
    assert incidents[0]["type"] == "INCIDENT_RAPID_DECELERATION"
    # Physical human emergency braking limit clamp: >= -10.0 m/s^2
    assert incidents[0]["deceleration_mps2"] >= -10.0


def test_vehicle_counter_accumulates_pedestrian_crowd_metrics():
    counter = VehicleCounter()
    peds = [
        DetectionBox(x1=10, y1=10, x2=20, y2=40, confidence=0.85, class_id=0, class_name="pedestrian"),
        DetectionBox(x1=30, y1=10, x2=40, y2=40, confidence=0.85, class_id=0, class_name="pedestrian")
    ]
    counter.update_pedestrian_counts(peds)
    crowd = counter.get_crowd_density(roi_area_sqm=50.0)
    assert crowd["pedestrian_count"] == 2
    assert crowd["density_sqm"] == 0.04
    assert crowd["fruin_los"] == "LOS A (Free Flow)"

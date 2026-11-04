"""
tests/test_incident_detector.py - Unit Tests for Real-Time Incident Detector
Validates stalled vehicle dwell time, wrong-way heading vectors, and deceleration shockwaves.
"""

import pytest
from traffic_system.computer_vision.schemas import DetectionBox
from traffic_system.computer_vision.incident_detector import IncidentDetector


def test_stalled_vehicle_detection():
    detector = IncidentDetector(stall_dwell_sec=2.0, stall_speed_threshold_kmh=2.0)
    box = DetectionBox(x1=200.0, y1=300.0, x2=280.0, y2=380.0, confidence=0.90, class_id=2, class_name="car")

    # Frame 0: first seen, speed 0 km/h
    inc0 = detector.update(track_id=1, box=box, speed_kmh=0.0, frame_idx=0, fps=10.0)
    assert len(inc0) == 0

    # Frame 15: 1.5 seconds later (still below 2.0s threshold)
    inc15 = detector.update(track_id=1, box=box, speed_kmh=0.0, frame_idx=15, fps=10.0)
    assert len(inc15) == 0

    # Frame 25: 2.5 seconds later (exceeds 2.0s threshold) -> Triggers stall incident
    inc25 = detector.update(track_id=1, box=box, speed_kmh=0.0, frame_idx=25, fps=10.0)
    assert len(inc25) == 1
    assert inc25[0]["type"] == "INCIDENT_STALLED_VEHICLE"
    assert inc25[0]["severity"] == "High"
    assert inc25[0]["track_id"] == 1


def test_wrong_way_detection():
    # Lane bearing is downwards (π/2, 90 degrees)
    detector = IncidentDetector(wrong_way_angle_deg=130.0, wrong_way_min_frames=3)

    # Simulate vehicle moving upwards (against lane bearing) over consecutive frames
    incidents = []
    for f in range(8):
        # Moving upwards: y decreases from 500 to 420
        box = DetectionBox(x1=300.0, y1=500.0 - f * 10, x2=360.0, y2=560.0 - f * 10, confidence=0.90, class_id=2, class_name="car")
        inc = detector.update(track_id=2, box=box, speed_kmh=35.0, frame_idx=f, fps=10.0, lane_bearing_rad=1.5708)
        incidents.extend(inc)

    # After at least 3 frames of wrong-way movement, incident should trigger
    ww_incidents = [i for i in incidents if i["type"] == "INCIDENT_WRONG_WAY_HAZARD"]
    assert len(ww_incidents) >= 1
    assert ww_incidents[0]["severity"] == "Critical"


def test_rapid_deceleration_shockwave():
    detector = IncidentDetector(decel_shockwave_threshold_mps2=-3.8)
    box = DetectionBox(x1=200.0, y1=200.0, x2=260.0, y2=260.0, confidence=0.90, class_id=2, class_name="car")

    # Frame 0: 60 km/h (~16.67 m/s)
    detector.update(track_id=3, box=box, speed_kmh=60.0, frame_idx=0, fps=10.0)

    # Frame 5: 0.5s later, sudden drop to 15 km/h (~4.17 m/s)
    # Δv = -12.5 m/s over 0.5s = -25.0 m/s^2 (severe shockwave)
    inc = detector.update(track_id=3, box=box, speed_kmh=15.0, frame_idx=5, fps=10.0)

    decel_incidents = [i for i in inc if i["type"] == "INCIDENT_RAPID_DECELERATION"]
    assert len(decel_incidents) == 1
    assert decel_incidents[0]["severity"] == "Advisory"


def test_camera_specific_calibrated_lane_bearing():
    # Calibrated lane direction is heading EAST (0 degrees / 0 radians)
    detector = IncidentDetector(expected_lane_bearings_deg=[0.0], wrong_way_angle_deg=120.0, wrong_way_min_frames=3)

    # Vehicle moving WEST (heading ~180 degrees, completely opposite to EAST)
    incidents = []
    for f in range(6):
        box = DetectionBox(x1=500.0 - f * 20, y1=300.0, x2=560.0 - f * 20, y2=360.0, confidence=0.9, class_id=2, class_name="car")
        inc = detector.update(track_id=10, box=box, speed_kmh=40.0, frame_idx=f, fps=10.0)
        incidents.extend(inc)

    ww = [i for i in incidents if i["type"] == "INCIDENT_WRONG_WAY_HAZARD"]
    assert len(ww) >= 1
    assert "calibrated flow" in ww[0]["message"]

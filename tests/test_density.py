"""
tests/test_density.py - Unit Tests for Roadway Traffic Density Estimation
"""

from traffic_system.computer_vision.density_estimator import TrafficDensityEstimator
from traffic_system.computer_vision.schemas import DetectionBox


def test_density_estimator_empty_frame():
    estimator = TrafficDensityEstimator()
    res = estimator.estimate([], frame_width=1280, frame_height=720)

    assert res["vehicles_in_roi"] == 0
    assert res["occupancy_pct"] == 0.0
    assert res["density_level"] == "Low"


def test_density_estimator_roi_inclusion_and_exclusion():
    # ROI default: y from 0.30 to 0.95 (216 to 684), x from 0.10 to 0.90 (128 to 1152)
    estimator = TrafficDensityEstimator()

    # Box 1: inside ROI (x: 200..300, y: 300..400)
    inside_box = DetectionBox(200, 300, 300, 400, 0.9, 2, "car", track_id=1)

    # Box 2: outside ROI (in top sky/canopy area y: 20..50)
    outside_box = DetectionBox(200, 20, 300, 50, 0.9, 2, "car", track_id=2)

    res = estimator.estimate([inside_box, outside_box], frame_width=1280, frame_height=720)
    assert res["vehicles_in_roi"] == 1
    assert res["occupancy_pct"] > 0.0


def test_density_estimator_congestion_scaling():
    estimator = TrafficDensityEstimator()

    # Pack 15 vehicles into the ROI to trigger Severe congestion
    dense_boxes = [
        DetectionBox(150 + (i % 5) * 180, 250 + (i // 5) * 120, 300 + (i % 5) * 180, 350 + (i // 5) * 120, 0.9, 5, "bus", track_id=i)
        for i in range(15)
    ]
    res = estimator.estimate(dense_boxes, frame_width=1280, frame_height=720)
    assert res["vehicles_in_roi"] == 15
    assert res["density_level"] in ("High", "Severe")


def test_density_estimator_camera_roi_profile_and_methodology():
    custom_roi = (0.50, 0.90, 0.20, 0.80)
    estimator = TrafficDensityEstimator(camera_id="cam_mg_road", roi_relative=custom_roi)
    res = estimator.estimate([], frame_width=1000, frame_height=1000)

    assert res["camera_id"] == "cam_mg_road"
    assert res["is_calibrated_physical_density"] is False
    assert res["measurement_type"] == "heuristic_optical_occupancy"
    assert "heuristic" in res["methodology_note"].lower()
    assert res["roi_coordinates"]["x1"] == 200.0
    assert res["roi_coordinates"]["x2"] == 800.0
    assert res["roi_coordinates"]["y1"] == 500.0
    assert res["roi_coordinates"]["y2"] == 900.0

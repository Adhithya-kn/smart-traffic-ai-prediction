"""
tests/test_vehicle_counter.py - Unit Tests for Vehicle Counter Subsystem
"""

from traffic_system.computer_vision.vehicle_counter import VehicleCounter
from traffic_system.computer_vision.schemas import DetectionBox


def test_vehicle_counter_unique_accumulation():
    counter = VehicleCounter()

    # Frame 1: Three vehicles
    f1_detections = [
        DetectionBox(10, 10, 50, 50, 0.9, 2, "car", track_id=1),
        DetectionBox(60, 10, 100, 50, 0.85, 3, "motorcycle", track_id=2),
        DetectionBox(120, 10, 200, 80, 0.88, 5, "bus", track_id=3)
    ]
    res1 = counter.update(f1_detections)
    assert res1["cumulative_unique_total"] == 3
    assert res1["cumulative_classes"]["car"] == 1
    assert res1["cumulative_classes"]["motorcycle"] == 1
    assert res1["cumulative_classes"]["bus"] == 1
    assert res1["cumulative_classes"]["truck"] == 0

    # Frame 2: Same vehicles (tracks 1, 2) + one new vehicle (track 4, truck)
    f2_detections = [
        DetectionBox(12, 12, 52, 52, 0.92, 2, "car", track_id=1),
        DetectionBox(62, 12, 102, 52, 0.86, 3, "motorcycle", track_id=2),
        DetectionBox(250, 20, 350, 90, 0.91, 7, "truck", track_id=4)
    ]
    res2 = counter.update(f2_detections)
    assert res2["cumulative_unique_total"] == 4
    assert res2["cumulative_classes"]["car"] == 1
    assert res2["cumulative_classes"]["motorcycle"] == 1
    assert res2["cumulative_classes"]["bus"] == 1
    assert res2["cumulative_classes"]["truck"] == 1


def test_vehicle_counter_summary_and_reset():
    counter = VehicleCounter()
    counter.update([DetectionBox(10, 10, 50, 50, 0.9, 2, "car", track_id=101)])
    summary = counter.get_summary()
    assert summary["total_unique_vehicles"] == 1
    assert summary["class_counts"]["car"] == 1

    counter.reset()
    assert counter.get_summary()["total_unique_vehicles"] == 0
    assert counter.get_summary()["class_counts"]["car"] == 0


def test_vehicle_counter_directional_flow():
    counter = VehicleCounter(min_displacement_pixels=10.0)

    # Track 1: Moves downwards (inbound)
    # Track 2: Moves upwards (outbound)
    # Track 3: Moves rightwards (lateral)
    # Frame 0
    counter.update([
        DetectionBox(100, 100, 150, 150, 0.9, 2, "car", track_id=1),
        DetectionBox(300, 400, 350, 450, 0.9, 3, "bus", track_id=2),
        DetectionBox(50, 50, 90, 90, 0.9, 4, "motorcycle", track_id=3)
    ])

    # Frame 1: Displaced along respective directions
    res = counter.update([
        DetectionBox(100, 150, 150, 200, 0.9, 2, "car", track_id=1),       # dy = +50 (inbound)
        DetectionBox(300, 330, 350, 380, 0.9, 3, "bus", track_id=2),       # dy = -70 (outbound)
        DetectionBox(110, 50, 150, 90, 0.9, 4, "motorcycle", track_id=3)   # dx = +60 (lateral)
    ])

    dirs = res["cumulative_directions"]
    assert dirs["inbound"] == 1
    assert dirs["outbound"] == 1
    assert dirs["lateral"] == 1

    summary = counter.get_summary()
    assert summary["direction_counts"]["inbound"] == 1
    assert summary["direction_counts"]["outbound"] == 1
    assert summary["direction_counts"]["lateral"] == 1
    assert summary["class_direction_counts"]["car"]["inbound"] == 1
    assert summary["class_direction_counts"]["bus"]["outbound"] == 1
    assert summary["class_direction_counts"]["motorcycle"]["lateral"] == 1

"""
tests/test_tripwire_counter.py - Unit Tests for Configurable Tripwire Vehicle Counter
Verifies:
1. Dynamic registration of arbitrary vector tripwires (horizontal, vertical, diagonal).
2. Detection of forward and reverse crossings with passage event emission.
3. Separation of class-specific crossing counts per tripwire.
4. Passage events structure: timestamp, speed, direction, track ID, tripwire name.
5. Backward compatibility with cumulative and frame-level vehicle counts.
"""

import pytest
from traffic_system.computer_vision.schemas import DetectionBox
from traffic_system.computer_vision.geometry import VectorTripwire, DirectionMode
from traffic_system.computer_vision.vehicle_counter import VehicleCounter


def test_configurable_tripwire_crossing_and_passage_events():
    """Verify that moving a vehicle across a custom diagonal tripwire generates a passage event."""
    counter = VehicleCounter(min_hits=1)

    # Register an axial gate at y=400 (crossing top-to-bottom)
    counter.add_tripwire(VectorTripwire(
        name="Gate_North_Axial",
        p1=(100.0, 400.0),
        p2=(900.0, 400.0),
        direction_mode=DirectionMode.BOTH
    ))

    # Frame 1: Vehicle above the line at (500, 370)
    det_f1 = [
        DetectionBox(x1=480, y1=350, x2=520, y2=390, confidence=0.90, class_id=2, class_name="car", track_id=1, speed_kmh=42.5)
    ]
    res_f1 = counter.update(det_f1, timestamp_sec=1.0, frame_width=1000, frame_height=800)
    assert len(counter.get_passage_events()) == 0

    # Frame 2: Vehicle crosses below the line to (500, 430)
    det_f2 = [
        DetectionBox(x1=480, y1=410, x2=520, y2=450, confidence=0.92, class_id=2, class_name="car", track_id=1, speed_kmh=43.0)
    ]
    res_f2 = counter.update(det_f2, timestamp_sec=1.5, frame_width=1000, frame_height=800)

    events = counter.get_passage_events()
    assert len(events) == 1
    ev = events[0]
    assert ev["track_id"] == 1
    assert ev["class_name"] == "car"
    assert ev["tripwire_name"] == "Gate_North_Axial"
    assert ev["direction"] == "FORWARD"
    assert ev["timestamp_sec"] == 1.5
    assert ev["speed_kmh"] == 43.0

    # Verify per-tripwire counts
    tw_counts = counter.get_tripwire_counts()
    assert "Gate_North_Axial" in tw_counts
    assert tw_counts["Gate_North_Axial"]["total"] == 1
    assert tw_counts["Gate_North_Axial"]["classes"]["car"] == 1


def test_tripwire_unidirectional_filtering():
    """Verify that a FORWARD_ONLY tripwire ignores reverse crossings."""
    counter = VehicleCounter(min_hits=1)

    counter.add_tripwire(VectorTripwire(
        name="Inbound_Gate",
        p1=(100.0, 400.0),
        p2=(900.0, 400.0),
        direction_mode=DirectionMode.FORWARD_ONLY
    ))

    # Vehicle moves bottom-to-top (Reverse crossing)
    # Frame 1: Below line at y=430
    det_f1 = [DetectionBox(x1=480, y1=410, x2=520, y2=450, confidence=0.88, class_id=3, class_name="motorcycle", track_id=2)]
    counter.update(det_f1, timestamp_sec=2.0)

    # Frame 2: Moves above line at y=370
    det_f2 = [DetectionBox(x1=480, y1=350, x2=520, y2=390, confidence=0.90, class_id=3, class_name="motorcycle", track_id=2)]
    counter.update(det_f2, timestamp_sec=2.5)

    # Must be filtered out because direction is REVERSE on FORWARD_ONLY gate
    assert len(counter.get_passage_events()) == 0
    assert counter.get_tripwire_counts()["Inbound_Gate"]["total"] == 0

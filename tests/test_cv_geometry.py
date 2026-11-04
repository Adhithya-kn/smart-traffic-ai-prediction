"""
tests/test_cv_geometry.py - Comprehensive Unit Tests for 2D Spatial Vector Geometry
Tests vector tripwires, directional line crossings via 2D cross products,
and polygonal zone occupancy containment.
"""

import pytest
from traffic_system.computer_vision.geometry import (
    Point2D,
    VectorTripwire,
    PolygonalZone,
    DirectionMode
)


def test_point2d_instantiation():
    pt = Point2D(100.5, 200.25)
    assert pt.x == 100.5
    assert pt.y == 200.25
    assert pt.as_tuple() == (100.5, 200.25)


def test_tripwire_forward_horizontal_crossing():
    """
    Tripwire is a vertical line at x=500 from y=100 to y=600.
    Normal vector points left-to-right (FORWARD).
    """
    tripwire = VectorTripwire(
        name="Line_Main_Corridor",
        p1=(500.0, 100.0),
        p2=(500.0, 600.0),
        direction_mode=DirectionMode.BOTH
    )

    # Crosses left-to-right (Forward)
    crossing = tripwire.check_crossing((480.0, 300.0), (520.0, 300.0))
    assert crossing == "FORWARD"

    # Crosses right-to-left (Reverse)
    crossing_rev = tripwire.check_crossing((520.0, 300.0), (480.0, 300.0))
    assert crossing_rev == "REVERSE"


def test_tripwire_vertical_flow_crossing():
    """
    Tripwire is a horizontal line at y=400 from x=200 to x=800.
    Top-to-bottom motion is standard CCTV corridor flow.
    """
    tripwire = VectorTripwire(
        name="Axial_Gate",
        p1=(200.0, 400.0),
        p2=(800.0, 400.0),
        direction_mode=DirectionMode.FORWARD_ONLY
    )

    # Top-to-bottom crossing (Forward)
    crossing = tripwire.check_crossing((450.0, 380.0), (450.0, 420.0))
    assert crossing == "FORWARD"

    # Bottom-to-top crossing (Reverse) - should return None because of FORWARD_ONLY
    crossing_rev = tripwire.check_crossing((450.0, 420.0), (450.0, 380.0))
    assert crossing_rev is None


def test_tripwire_non_crossing_cases():
    tripwire = VectorTripwire(
        name="Gate_Test",
        p1=(100.0, 100.0),
        p2=(500.0, 100.0),
        direction_mode=DirectionMode.BOTH
    )

    # Trajectory stays above the line
    assert tripwire.check_crossing((200.0, 50.0), (300.0, 70.0)) is None

    # Trajectory crosses line projection, but beyond endpoints (misses gate)
    assert tripwire.check_crossing((550.0, 80.0), (550.0, 120.0)) is None


def test_polygonal_zone_containment():
    """
    Square carriage zone with corners at (100, 100), (300, 100), (300, 300), (100, 300).
    """
    poly = [(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]
    zone = PolygonalZone(name="Junction_Box", polygon_points=poly)

    # Point clearly inside
    assert zone.contains_point((200.0, 200.0)) is True

    # Point clearly outside
    assert zone.contains_point((50.0, 200.0)) is False
    assert zone.contains_point((200.0, 350.0)) is False

    # Triangle zone
    triangle = [(0.0, 0.0), (100.0, 0.0), (50.0, 100.0)]
    t_zone = PolygonalZone(name="Triangle_Merge", polygon_points=triangle)
    assert t_zone.contains_point((50.0, 30.0)) is True
    assert t_zone.contains_point((10.0, 90.0)) is False

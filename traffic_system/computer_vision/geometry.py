"""
traffic_system/computer_vision/geometry.py - 2D Spatial Vector Geometry Engine
Provides directional polyline tripwires and polygonal spatial zone containment
using 2D vector cross-products and ray-casting algorithms.
"""

from enum import Enum
from typing import Tuple, List, Optional, NamedTuple


class DirectionMode(str, Enum):
    BOTH = "BOTH"
    FORWARD_ONLY = "FORWARD_ONLY"
    REVERSE_ONLY = "REVERSE_ONLY"


class Point2D(NamedTuple):
    x: float
    y: float

    def as_tuple(self) -> Tuple[float, float]:
        return (float(self.x), float(self.y))


def _cross_product_2d(ox: float, oy: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Computes 2D vector cross product: (A - O) x (B - O) = (Ax - Ox)*(By - Oy) - (Ay - Oy)*(Bx - Ox)."""
    return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)


def _segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float]
) -> bool:
    """Determines whether line segment (p1, p2) intersects segment (p3, p4)."""
    d1 = _cross_product_2d(p3[0], p3[1], p4[0], p4[1], p1[0], p1[1])
    d2 = _cross_product_2d(p3[0], p3[1], p4[0], p4[1], p2[0], p2[1])
    d3 = _cross_product_2d(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
    d4 = _cross_product_2d(p1[0], p1[1], p2[0], p2[1], p4[0], p4[1])

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True

    # Check collinear endpoint touch
    def on_segment(px, py, qx, qy, rx, ry):
        return (min(px, rx) <= qx <= max(px, rx)) and (min(py, ry) <= qy <= max(py, ry))

    if abs(d1) < 1e-9 and on_segment(p3[0], p3[1], p1[0], p1[1], p4[0], p4[1]):
        return True
    if abs(d2) < 1e-9 and on_segment(p3[0], p3[1], p2[0], p2[1], p4[0], p4[1]):
        return True
    if abs(d3) < 1e-9 and on_segment(p1[0], p1[1], p3[0], p3[1], p2[0], p2[1]):
        return True
    if abs(d4) < 1e-9 and on_segment(p1[0], p1[1], p4[0], p4[1], p2[0], p2[1]):
        return True

    return False


class VectorTripwire:
    """
    Arbitrary 2D directed tripwire line segment defining vehicle crossing boundaries.
    Uses vector intersection to detect line crossing and determines FORWARD vs REVERSE
    crossing direction relative to corridor flow orientation or explicit forward_vector.
    """
    def __init__(
        self,
        name: str,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        direction_mode: DirectionMode = DirectionMode.BOTH,
        forward_vector: Optional[Tuple[float, float]] = None
    ):
        self.name = name
        self.p1 = Point2D(float(p1[0]), float(p1[1]))
        self.p2 = Point2D(float(p2[0]), float(p2[1]))
        self.direction_mode = direction_mode
        self.forward_vector = forward_vector

    def check_crossing(
        self,
        prev_point: Tuple[float, float],
        curr_point: Tuple[float, float]
    ) -> Optional[str]:
        """
        Evaluates whether a moving trajectory segment (prev_point -> curr_point)
        crossed this tripwire, and if so, returns crossing direction: 'FORWARD' or 'REVERSE'.
        Returns None if no crossing occurred or if crossing direction is filtered by direction_mode.
        """
        t1, t2 = (self.p1.x, self.p1.y), (self.p2.x, self.p2.y)
        c1, c2 = (float(prev_point[0]), float(prev_point[1])), (float(curr_point[0]), float(curr_point[1]))

        if not _segments_intersect(t1, t2, c1, c2):
            return None

        dx = c2[0] - c1[0]
        dy = c2[1] - c1[1]

        if self.forward_vector is not None:
            dot = dx * self.forward_vector[0] + dy * self.forward_vector[1]
            direction = "FORWARD" if dot >= 0 else "REVERSE"
        else:
            # Default convention:
            # For mostly vertical lines, moving left-to-right (+dx) is FORWARD.
            # For mostly horizontal lines, moving top-to-bottom (+dy) is FORWARD.
            line_dx = abs(t2[0] - t1[0])
            line_dy = abs(t2[1] - t1[1])
            if line_dy >= line_dx:
                direction = "FORWARD" if dx >= 0 else "REVERSE"
            else:
                direction = "FORWARD" if dy >= 0 else "REVERSE"

        if self.direction_mode == DirectionMode.FORWARD_ONLY and direction != "FORWARD":
            return None
        if self.direction_mode == DirectionMode.REVERSE_ONLY and direction != "REVERSE":
            return None

        return direction


class PolygonalZone:
    """
    Polygonal roadway presence zone (e.g. carriage-way, queue zone, junction box).
    Evaluates spatial vehicle containment using the Jordan Curve Ray-Casting algorithm.
    """
    def __init__(self, name: str, polygon_points: List[Tuple[float, float]]):
        self.name = name
        self.points = [Point2D(float(pt[0]), float(pt[1])) for pt in polygon_points]
        if len(self.points) < 3:
            raise ValueError(f"PolygonalZone '{name}' requires at least 3 vertices.")

    def contains_point(self, pt: Tuple[float, float]) -> bool:
        """Determines if 2D coordinate is inside the polygon using ray-casting."""
        x, y = float(pt[0]), float(pt[1])
        n = len(self.points)
        inside = False

        p1 = self.points[0]
        for i in range(1, n + 1):
            p2 = self.points[i % n]
            if y > min(p1.y, p2.y):
                if y <= max(p1.y, p2.y):
                    if x <= max(p1.x, p2.x):
                        if p1.y != p2.y:
                            x_inters = (y - p1.y) * (p2.x - p1.x) / (p2.y - p1.y) + p1.x
                            if p1.x == p2.x or x <= x_inters:
                                inside = not inside
            p1 = p2

        return inside

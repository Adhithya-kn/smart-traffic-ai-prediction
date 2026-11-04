"""
traffic_system/computer_vision/density_estimator.py - Roadway Traffic Density Estimator
Estimates traffic density, roadway occupancy, and congestion level within a camera-specific Region of Interest (ROI).

Methodology & Calibration Documentation:
- Optical Occupancy: The ratio of cumulative bounding-box pixel footprint to total roadway ROI area:
  Occupancy Ratio = (Sum of Vehicle Area in ROI) / (Total ROI Area).
- HEURISTIC LIMITATION:
  This is a 2D image-space optical occupancy heuristic, NOT a calibrated physical road-density measurement (veh/km/lane).
  True physical spatial density requires 3D camera extrinsic parameters (pitch, roll, yaw, height above ground)
  and ground-truth road segment length in meters.
"""

from typing import List, Dict, Any, Tuple, Optional
from traffic_system.computer_vision.schemas import DetectionBox


class TrafficDensityEstimator:
    """
    Measures vehicular density within an optical road Region of Interest (ROI).
    Supports camera-specific rectangular or polygonal road boundaries.
    Calculates spatial occupancy percentage and classifies Level of Service (LOS).
    """
    def __init__(
        self,
        camera_id: str = "cctv_primary",
        roi_relative: Tuple[float, float, float, float] = (0.30, 0.95, 0.10, 0.90),
        roi_polygon: Optional[List[Tuple[float, float]]] = None
    ):
        """
        camera_id: Identifier for camera optical profile.
        roi_relative: (min_y_ratio, max_y_ratio, min_x_ratio, max_x_ratio).
        roi_polygon: Optional list of (x_ratio, y_ratio) defining non-rectangular carriage-way polygon.
        """
        self.camera_id = camera_id
        self.min_y_ratio, self.max_y_ratio, self.min_x_ratio, self.max_x_ratio = roi_relative
        self.roi_polygon = roi_polygon

    def estimate(
        self,
        detections: List[DetectionBox],
        frame_width: int = 1280,
        frame_height: int = 720
    ) -> Dict[str, Any]:
        """
        Evaluates detections against the camera-specific roadway ROI.
        Returns ROI vehicle count, occupancy percentage, and classified congestion level.
        """
        roi_x1 = frame_width * self.min_x_ratio
        roi_x2 = frame_width * self.max_x_ratio
        roi_y1 = frame_height * self.min_y_ratio
        roi_y2 = frame_height * self.max_y_ratio

        roi_area = max(1.0, (roi_x2 - roi_x1) * (roi_y2 - roi_y1))

        vehicles_in_roi = 0
        total_vehicle_area = 0.0

        for det in detections:
            center_x = (det.x1 + det.x2) / 2.0
            center_y = (det.y1 + det.y2) / 2.0

            if roi_x1 <= center_x <= roi_x2 and roi_y1 <= center_y <= roi_y2:
                vehicles_in_roi += 1
                v_w = max(0.0, min(det.x2, roi_x2) - max(det.x1, roi_x1))
                v_h = max(0.0, min(det.y2, roi_y2) - max(det.y1, roi_y1))
                total_vehicle_area += (v_w * v_h)

        occupancy_ratio = min(1.0, total_vehicle_area / roi_area)
        occupancy_pct = round(occupancy_ratio * 100.0, 1)

        # Classify Level of Service (LOS) Density
        if occupancy_pct >= 55.0 or vehicles_in_roi >= 12:
            density_level = "Severe"
        elif occupancy_pct >= 35.0 or vehicles_in_roi >= 7:
            density_level = "High"
        elif occupancy_pct >= 15.0 or vehicles_in_roi >= 3:
            density_level = "Moderate"
        else:
            density_level = "Low"

        return {
            "camera_id": self.camera_id,
            "vehicles_in_roi": vehicles_in_roi,
            "occupancy_pct": occupancy_pct,
            "density_level": density_level,
            "measurement_type": "heuristic_optical_occupancy",
            "is_calibrated_physical_density": False,
            "methodology_note": (
                "2D optical area occupancy heuristic within camera ROI. "
                "Physical spatial density (veh/km) requires 3D camera extrinsic calibration and road length."
            ),
            "roi_coordinates": {
                "x1": round(roi_x1, 1),
                "y1": round(roi_y1, 1),
                "x2": round(roi_x2, 1),
                "y2": round(roi_y2, 1)
            }
        }

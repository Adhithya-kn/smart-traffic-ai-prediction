"""
traffic_system/computer_vision/density_estimator.py - Roadway Traffic Density Estimator
Estimates traffic density, roadway occupancy, and congestion level within a Region of Interest (ROI).
"""

from typing import List, Dict, Any, Tuple, Optional
from traffic_system.computer_vision.schemas import DetectionBox


class TrafficDensityEstimator:
    """
    Measures vehicular density within an optical road Region of Interest (ROI).
    Calculates spatial occupancy percentage and classifies Level of Service (LOS).
    """
    def __init__(
        self,
        roi_relative: Tuple[float, float, float, float] = (0.30, 0.95, 0.10, 0.90)
    ):
        """
        roi_relative: (min_y_ratio, max_y_ratio, min_x_ratio, max_x_ratio)
        Default focuses on the primary carriage roadway (bottom 65% of frame).
        """
        self.min_y_ratio, self.max_y_ratio, self.min_x_ratio, self.max_x_ratio = roi_relative

    def estimate(
        self,
        detections: List[DetectionBox],
        frame_width: int = 1280,
        frame_height: int = 720
    ) -> Dict[str, Any]:
        """
        Evaluates detections against the roadway ROI.
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
            "vehicles_in_roi": vehicles_in_roi,
            "occupancy_pct": occupancy_pct,
            "density_level": density_level,
            "roi_coordinates": {
                "x1": round(roi_x1, 1),
                "y1": round(roi_y1, 1),
                "x2": round(roi_x2, 1),
                "y2": round(roi_y2, 1)
            }
        }

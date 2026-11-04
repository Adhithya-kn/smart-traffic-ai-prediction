"""
traffic_system/computer_vision/speed_estimator.py - Kinematic Speed Estimation
Calculates vehicle velocity using camera-specific planar homography with bottom-center tire contact
anchoring, discretization jitter suppression, and Exponential Moving Average (EMA) smoothing.

Methodology & Calibration Invariants:
- Pixel movement alone does NOT establish physical speed without verified camera-specific calibration.
- Generic default homography cannot be assumed valid for arbitrary sample videos.
- If camera calibration is absent, speed outputs are explicitly tagged as uncalibrated optical proxies.
"""

from typing import Dict, Any, Tuple, Optional, List
import numpy as np
from traffic_system.computer_vision.schemas import DetectionBox


# Generic Perspective Homography Reference Matrix
# (Only used as uncalibrated baseline; NOT assumed valid as verified physical speed)
GENERIC_HOMOGRAPHY_REFERENCE = np.array([
    [0.0245, -0.0012, -7.85],
    [0.0008,  0.0382, -12.40],
    [0.00001, 0.00045, 1.00]
], dtype=np.float64)


class SpeedEstimator:
    """
    Kinematic speed estimation engine using camera-specific perspective projection.
    Requires camera-specific calibration (homography or 4-point correspondence) before reporting true speed.
    Anchors to bottom-center tire contact point to avoid vehicle height parallax.
    """
    def __init__(
        self,
        camera_id: str = "uncalibrated_cctv",
        homography_matrix: Optional[np.ndarray] = None,
        is_calibrated: bool = False,
        pixels_per_meter: float = 12.5,
        ema_alpha: float = 0.30,
        min_displacement_m: float = 0.35,
        max_valid_speed_kmh: float = 140.0
    ):
        self.camera_id = camera_id
        self.is_calibrated = is_calibrated or (homography_matrix is not None)
        self.homography = homography_matrix if homography_matrix is not None else GENERIC_HOMOGRAPHY_REFERENCE
        self.pixels_per_meter = pixels_per_meter
        self.ema_alpha = ema_alpha
        self.min_displacement_m = min_displacement_m
        self.max_valid_speed_kmh = max_valid_speed_kmh

        # History tracking: track_id -> List of (frame_idx, ground_x, ground_y, smoothed_speed)
        self.track_history: Dict[int, List[Tuple[int, float, float, float]]] = {}

    @classmethod
    def from_four_point_correspondence(
        cls,
        src_points: List[Tuple[float, float]],
        dst_points_meters: List[Tuple[float, float]],
        camera_id: str = "calibrated_cctv"
    ) -> "SpeedEstimator":
        """
        Derives camera-specific planar homography from 4 known image points (pixels)
        and 4 ground metric coordinates (meters).
        Uses Direct Linear Transformation (DLT).
        """
        if len(src_points) != 4 or len(dst_points_meters) != 4:
            raise ValueError("Direct Linear Transformation requires exactly 4 point correspondences.")

        A = []
        for (u, v), (x, y) in zip(src_points, dst_points_meters):
            A.append([-u, -v, -1.0, 0.0, 0.0, 0.0, u * x, v * x, x])
            A.append([0.0, 0.0, 0.0, -u, -v, -1.0, u * y, v * y, y])
        A = np.array(A, dtype=np.float64)

        # Singular Value Decomposition to solve Ah = 0
        _, _, Vh = np.linalg.svd(A)
        H = Vh[-1].reshape((3, 3))
        H = H / H[2, 2]

        return cls(camera_id=camera_id, homography_matrix=H, is_calibrated=True)

    def set_calibration(self, homography_matrix: np.ndarray, camera_id: str = "calibrated_camera"):
        """Updates camera-specific homography calibration."""
        self.homography = np.array(homography_matrix, dtype=np.float64)
        self.is_calibrated = True
        self.camera_id = camera_id
        self.reset()

    def get_calibration_status(self) -> Dict[str, Any]:
        """Reports camera calibration status and speed estimation mode."""
        return {
            "camera_id": self.camera_id,
            "is_calibrated": self.is_calibrated,
            "speed_mode": "calibrated_planar_homography" if self.is_calibrated else "uncalibrated_optical_proxy",
            "warning": None if self.is_calibrated else (
                "Camera homography uncalibrated for this specific video. "
                "Reported speeds represent an optical proxy, not verified physical ground velocity."
            )
        }

    def project_ground_point(self, u: float, v: float) -> Tuple[float, float]:
        """Projects image pixel point (u, v) onto world ground coordinates (X, Y) in meters."""
        img_pt = np.array([u, v, 1.0], dtype=np.float64)
        world_pt = self.homography @ img_pt
        w = world_pt[2] if abs(world_pt[2]) > 1e-6 else 1e-6
        return float(world_pt[0] / w), float(world_pt[1] / w)

    def project_point(self, u: float, v: float) -> Tuple[float, float]:
        """Alias for project_ground_point."""
        return self.project_ground_point(u, v)

    def estimate_speed(
        self,
        track_id: int,
        box: DetectionBox,
        frame_idx: int,
        fps: float = 30.0
    ) -> float:
        """Estimates vehicle speed in km/h from sequential frames using tire-contact projection."""
        fps_val = max(1.0, fps)
        # Tire-contact anchor: bottom-center of bounding box
        u_ground = (box.x1 + box.x2) / 2.0
        v_ground = box.y2

        gx, gy = self.project_ground_point(u_ground, v_ground)

        if track_id not in self.track_history:
            self.track_history[track_id] = [(frame_idx, gx, gy, 0.0)]
            return 0.0

        history = self.track_history[track_id]
        prev_frame, prev_x, prev_y, prev_speed = history[-1]
        delta_frames = frame_idx - prev_frame

        if delta_frames <= 0:
            return prev_speed

        delta_t = delta_frames / fps_val

        # Ground plane displacement in meters
        disp_m = float(np.sqrt((gx - prev_x) ** 2 + (gy - prev_y) ** 2))

        # Check total displacement across recent history (last 10 observations)
        if len(history) >= 5:
            first_in_window = history[-min(len(history), 10)]
            window_disp = float(np.sqrt((gx - first_in_window[1]) ** 2 + (gy - first_in_window[2]) ** 2))
            if window_disp < self.min_displacement_m:
                # Stationary vehicle jitter suppression
                smoothed_speed = 0.0
                history.append((frame_idx, gx, gy, smoothed_speed))
                if len(history) > 30:
                    history.pop(0)
                return 0.0

        # Instantaneous speed in km/h
        instant_speed = (disp_m / delta_t) * 3.6

        # Physical reasonableness sanity check
        if instant_speed > self.max_valid_speed_kmh:
            instant_speed = prev_speed

        # Exponential Moving Average (EMA) smoothing
        smoothed_speed = round(self.ema_alpha * instant_speed + (1.0 - self.ema_alpha) * prev_speed, 1)
        smoothed_speed = max(0.0, min(smoothed_speed, self.max_valid_speed_kmh))

        history.append((frame_idx, gx, gy, smoothed_speed))
        if len(history) > 30:
            history.pop(0)

        return smoothed_speed

    def reset(self) -> None:
        """Clears speed tracking history."""
        self.track_history.clear()

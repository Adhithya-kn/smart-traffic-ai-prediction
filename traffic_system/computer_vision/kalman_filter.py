"""
traffic_system/computer_vision/kalman_filter.py - 8-State Kalman Box Filter
Implements linear Kalman Filter for bounding box tracking in image space:
State vector: [x, y, a, h, vx, vy, va, vh]^T
Where (x, y) is the bounding box center, a is aspect ratio (w/h), h is height,
and (vx, vy, va, vh) are respective velocities under constant-velocity dynamics.
"""

import numpy as np
from typing import Tuple


def xyxy_to_xyah(box: np.ndarray) -> np.ndarray:
    """Converts [x1, y1, x2, y2] to [x_center, y_center, aspect_ratio (w/h), height]."""
    x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
    w = max(1.0, float(x2 - x1))
    h = max(1.0, float(y2 - y1))
    xc = float(x1 + w / 2.0)
    yc = float(y1 + h / 2.0)
    return np.array([xc, yc, w / h, h], dtype=np.float64)


def xyah_to_xyxy(state: np.ndarray) -> np.ndarray:
    """Converts [x_center, y_center, aspect_ratio (w/h), height] to [x1, y1, x2, y2]."""
    xc, yc, a, h = state[0], state[1], max(1e-4, state[2]), max(1.0, state[3])
    w = a * h
    return np.array([
        xc - w / 2.0,
        yc - h / 2.0,
        xc + w / 2.0,
        yc + h / 2.0
    ], dtype=np.float64)


class KalmanBoxFilter:
    """
    8-state Kalman Filter modeling vehicle 2D kinematics with constant velocity.
    State: [x, y, a, h, vx, vy, va, vh]
    Measurement: [x, y, a, h]
    """
    def __init__(self):
        self._motion_mat = np.eye(8, 8, dtype=np.float64)
        for i in range(4):
            self._motion_mat[i, i + 4] = 1.0

        self._update_mat = np.eye(4, 8, dtype=np.float64)

        self._std_weight_position = 1.0 / 20.0
        self._std_weight_velocity = 1.0 / 160.0

    def initiate(self, measurement: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Initializes Kalman state mean and covariance from first detection."""
        xyah = xyxy_to_xyah(measurement) if len(measurement) == 4 and measurement[2] > measurement[0] else measurement
        mean = np.zeros(8, dtype=np.float64)
        mean[:4] = xyah

        h = max(1.0, float(xyah[3]))
        std_p = [
            2.0 * self._std_weight_position * h,
            2.0 * self._std_weight_position * h,
            1e-2,
            2.0 * self._std_weight_position * h
        ]
        std_v = [
            10.0 * self._std_weight_velocity * h,
            10.0 * self._std_weight_velocity * h,
            1e-5,
            10.0 * self._std_weight_velocity * h
        ]

        cov = np.diag(np.square(std_p + std_v))
        return mean, cov

    def predict(self, mean: np.ndarray, covariance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Projects state and covariance forward one time step under constant velocity."""
        h = max(1.0, float(mean[3]))
        std_p = [
            self._std_weight_position * h,
            self._std_weight_position * h,
            1e-2,
            self._std_weight_position * h
        ]
        std_v = [
            self._std_weight_velocity * h,
            self._std_weight_velocity * h,
            1e-5,
            self._std_weight_velocity * h
        ]
        q = np.diag(np.square(std_p + std_v))

        mean_pred = np.dot(self._motion_mat, mean)
        cov_pred = np.linalg.multi_dot([self._motion_mat, covariance, self._motion_mat.T]) + q
        return mean_pred, cov_pred

    def project(self, mean: np.ndarray, covariance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Projects state to measurement space."""
        h = max(1.0, float(mean[3]))
        std = [
            self._std_weight_position * h,
            self._std_weight_position * h,
            1e-1,
            self._std_weight_position * h
        ]
        r = np.diag(np.square(std))

        proj_mean = np.dot(self._update_mat, mean)
        proj_cov = np.linalg.multi_dot([self._update_mat, covariance, self._update_mat.T]) + r
        return proj_mean, proj_cov

    def update(
        self,
        mean: np.ndarray,
        covariance: np.ndarray,
        measurement: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Corrects Kalman state and covariance using new measurement."""
        xyah = xyxy_to_xyah(measurement) if len(measurement) == 4 and measurement[2] > measurement[0] else measurement
        proj_mean, proj_cov = self.project(mean, covariance)

        # Kalman gain: K = P * H^T * inv(S)
        kalman_gain = np.linalg.multi_dot([
            covariance,
            self._update_mat.T,
            np.linalg.inv(proj_cov)
        ])

        innovation = xyah - proj_mean
        new_mean = mean + np.dot(kalman_gain, innovation)
        new_cov = covariance - np.linalg.multi_dot([kalman_gain, proj_cov, kalman_gain.T])
        return new_mean, new_cov

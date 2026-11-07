"""
traffic_system/core/camera_registry.py - Camera calibration registry.

A camera is the unit of physical calibration. It stores the corridor mapping,
ROI/lane polygons and a 4-point planar homography. Speeds/densities from an
uncalibrated camera are proxies and must not be used for physical claims.

The registry is mutable runtime state (var/cameras.json by default), never a
tracked artifact.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from traffic_system.config import RUNTIME_DATA_DIR
from traffic_system.core.fs_utils import atomic_json_dump, safe_read_json

CAMERAS_FILE = RUNTIME_DATA_DIR / "cameras.json"


class CameraRegistryError(ValueError):
    pass


class CameraRegistry:
    _instance: Optional["CameraRegistry"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "CameraRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = CameraRegistry()
            return cls._instance

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else CAMERAS_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.cameras: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        raw = safe_read_json(self.db_path, {})
        if isinstance(raw, dict):
            self.cameras = raw
        elif isinstance(raw, list):
            self.cameras = {str(c.get("camera_id")): c for c in raw if isinstance(c, dict) and c.get("camera_id")}
        if not self.cameras:
            self.cameras = {
                "CAM_BLR_01": {
                    "camera_id": "CAM_BLR_01",
                    "corridor_id": "RD_BLR_01",
                    "name": "Indiranagar 100 Feet Road CCTV #1",
                    "roi_polygon": [[0.05, 0.2], [0.95, 0.2], [0.95, 0.95], [0.05, 0.95]],
                    "lane_polygons": [
                        [[0.05, 0.2], [0.48, 0.2], [0.48, 0.95], [0.05, 0.95]],
                        [[0.52, 0.2], [0.95, 0.2], [0.95, 0.95], [0.52, 0.95]]
                    ],
                    "homography_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    "pixels_per_meter": 14.2,
                    "is_homography_calibrated": True,
                    "updated_at": time.time()
                },
                "CAM_BLR_02": {
                    "camera_id": "CAM_BLR_02",
                    "corridor_id": "RD_BLR_02",
                    "name": "MG Road - Trinity Circle CCTV #2",
                    "roi_polygon": [[0.1, 0.15], [0.9, 0.15], [0.95, 0.9], [0.05, 0.9]],
                    "lane_polygons": [],
                    "homography_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    "pixels_per_meter": 12.5,
                    "is_homography_calibrated": True,
                    "updated_at": time.time()
                },
                "CAM_BLR_03": {
                    "camera_id": "CAM_BLR_03",
                    "corridor_id": "RD_BLR_03",
                    "name": "Hebbal Flyover Express CCTV #3",
                    "roi_polygon": [[0.0, 0.1], [1.0, 0.1], [1.0, 1.0], [0.0, 1.0]],
                    "lane_polygons": [],
                    "homography_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    "pixels_per_meter": 16.0,
                    "is_homography_calibrated": True,
                    "updated_at": time.time()
                },
                "CAM_BLR_04": {
                    "camera_id": "CAM_BLR_04",
                    "corridor_id": "RD_BLR_04",
                    "name": "Electronic City Toll Gate CCTV #4",
                    "roi_polygon": [[0.05, 0.1], [0.95, 0.1], [0.95, 0.95], [0.05, 0.95]],
                    "lane_polygons": [],
                    "homography_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    "pixels_per_meter": 13.8,
                    "is_homography_calibrated": True,
                    "updated_at": time.time()
                }
            }
            self._save()

    def _save(self) -> None:
        atomic_json_dump(self.cameras, self.db_path)

    def list_cameras(self, corridor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = [dict(c) for c in self.cameras.values()]
        if corridor_id:
            items = [c for c in items if c.get("corridor_id") == corridor_id]
        return sorted(items, key=lambda c: c.get("camera_id", ""))

    def get(self, camera_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cam = self.cameras.get(str(camera_id))
            return dict(cam) if cam else None

    def upsert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise CameraRegistryError("Camera payload must be an object.")
        camera_id = str(payload.get("camera_id", "")).strip()
        corridor_id = str(payload.get("corridor_id", "")).strip()
        if not camera_id or not corridor_id:
            raise CameraRegistryError("camera_id and corridor_id are required.")
        if not (camera_id.replace("-", "").replace("_", "").isalnum() and len(camera_id) <= 80):
            raise CameraRegistryError("camera_id must be alphanumeric with dashes/underscores (max 80).")

        roi = payload.get("roi_polygon")
        lanes = payload.get("lane_polygons")
        for name, value in (("roi_polygon", roi), ("lane_polygons", lanes)):
            if value is not None and not isinstance(value, list):
                raise CameraRegistryError(f"{name} must be a list of points.")
        homography = payload.get("homography")
        if homography is not None:
            arr = np.array(homography, dtype=np.float64)
            if arr.shape != (3, 3) or not np.isfinite(arr).all():
                raise CameraRegistryError("homography must be a finite 3x3 matrix.")

        with self._lock:
            existing = self.cameras.get(camera_id, {})
            record = {
                **existing,
                "camera_id": camera_id,
                "corridor_id": corridor_id,
                "name": str(payload.get("name", existing.get("name", camera_id))),
                "roi_polygon": roi if roi is not None else existing.get("roi_polygon"),
                "lane_polygons": lanes if lanes is not None else existing.get("lane_polygons"),
                "homography_matrix": homography if homography is not None else existing.get("homography_matrix"),
                "pixels_per_meter": float(payload.get("pixels_per_meter", existing.get("pixels_per_meter", 12.5))),
                "is_homography_calibrated": bool(payload.get("is_homography_calibrated", existing.get("is_homography_calibrated", False))),
                "updated_at": time.time(),
            }
            self.cameras[camera_id] = record
            self._save()
            return dict(record)

    def calibrate(
        self,
        camera_id: str,
        src_points: List[Tuple[float, float]],
        dst_points_meters: List[Tuple[float, float]],
    ) -> Dict[str, Any]:
        if len(src_points) != 4 or len(dst_points_meters) != 4:
            raise CameraRegistryError("Exactly 4 source and 4 destination points are required.")
        src = np.array(src_points, dtype=np.float64)
        dst = np.array(dst_points_meters, dtype=np.float64)
        if not np.isfinite(src).all() or not np.isfinite(dst).all():
            raise CameraRegistryError("Calibration points must be finite numbers.")

        A = []
        for (u, v), (x, y) in zip(src, dst):
            A.append([-u, -v, -1.0, 0.0, 0.0, 0.0, u * x, v * x, x])
            A.append([0.0, 0.0, 0.0, -u, -v, -1.0, u * y, v * y, y])
        try:
            _, _, Vh = np.linalg.svd(np.array(A, dtype=np.float64))
            H = Vh[-1].reshape((3, 3))
            if abs(H[2, 2]) < 1e-12:
                raise CameraRegistryError("Degenerate calibration points (homography scale is zero).")
            H = H / H[2, 2]
        except np.linalg.LinAlgError as exc:
            raise CameraRegistryError(f"Calibration solve failed: {exc}") from exc

        # Reprojection error on the four control points.
        try:
            pts = np.column_stack([src, np.ones(len(src))])
            projected = (H @ pts.T).T
            projected = projected[:, :2] / projected[:, 2:3]
            reprojection = float(np.sqrt(np.mean(np.sum((projected - dst) ** 2, axis=1))))
        except Exception:
            reprojection = None

        with self._lock:
            existing = self.cameras.get(str(camera_id))
            if not existing:
                raise CameraRegistryError(f"Camera '{camera_id}' is not registered. Register it first.")
            existing.update({
                "homography_matrix": H.tolist(),
                "is_homography_calibrated": True,
                "calibration_points": {
                    "src_pixels": [list(map(float, p)) for p in src_points],
                    "dst_meters": [list(map(float, p)) for p in dst_points_meters],
                },
                "reprojection_error_px": round(reprojection, 3) if reprojection is not None else None,
                "calibrated_at": time.time(),
            })
            self._save()
            return dict(existing)


_REGISTRY: Optional[CameraRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def get_camera_registry() -> CameraRegistry:
    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is None:
            _REGISTRY = CameraRegistry.get_instance()
        return _REGISTRY

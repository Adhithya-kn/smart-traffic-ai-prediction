"""
traffic_system/computer_vision/schemas.py - Data Classes & Schemas for Vision Pipeline
Includes model status, provenance, camera/video configuration, and confidence summaries.
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from traffic_system.core.time_utils import now_iso


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


VEHICLE_CLASSES = {
    "car": "Car",
    "motorcycle": "Motorcycle",
    "bicycle": "Bicycle",
    "bus": "Bus",
    "truck": "Truck",
    "auto_rickshaw": "Auto-Rickshaw",
    "lcv": "Light Commercial Vehicle"
}


@dataclass(slots=True)
class TripwireConfig:
    name: str
    p1: Tuple[float, float]
    p2: Tuple[float, float]
    direction_mode: str = "BOTH"
    forward_vector: Optional[Tuple[float, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VehiclePassageEvent:
    passage_id: str
    track_id: int
    class_name: str
    tripwire_name: str
    direction: str
    timestamp_sec: float
    speed_kmh: float = 0.0
    frame_idx: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DetectionBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str
    track_id: Optional[int] = None
    speed_kmh: float = 0.0
    trajectory: List[Any] = field(default_factory=list)
    route_status: str = "APPROACHING"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CameraConfig:
    """Camera-specific optical profile and physical calibration configuration."""
    camera_id: str = "default_cctv"
    roi_relative: Tuple[float, float, float, float] = (0.30, 0.95, 0.10, 0.90)
    roi_polygon: Optional[List[Tuple[float, float]]] = None
    expected_lane_bearing_deg: float = 90.0  # 90 deg = downwards flow
    allowed_bearing_tolerance_deg: float = 55.0
    is_homography_calibrated: bool = False
    homography_matrix: Optional[List[List[float]]] = None
    pixels_per_meter: float = 12.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ConfidenceSummary:
    """Summary of detection confidence metrics across analyzed video frames."""
    detection_threshold: float
    mean_confidence: float
    min_confidence: float
    max_confidence: float
    total_detections: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FrameDetectionResult:
    frame_index: int
    timestamp_sec: float
    detections: List[DetectionBox]
    vehicle_count: int
    density_level: str
    roi_density_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "timestamp_sec": round(self.timestamp_sec, 2),
            "detections": [d.to_dict() for d in self.detections],
            "vehicle_count": self.vehicle_count,
            "density_level": self.density_level,
            "roi_density_pct": round(self.roi_density_pct, 1)
        }


@dataclass(slots=True)
class VisionJob:
    job_id: str
    video_id: str
    original_filename: str
    owner: str = ""
    status: JobStatus = JobStatus.PENDING
    progress_pct: float = 0.0
    total_frames: int = 0
    processed_frames: int = 0
    duration_seconds: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    model_name: str = "yolo11n.pt"
    model_status: str = "active"
    provenance: str = "Genuine YOLO inference"
    camera_config: Optional[Dict[str, Any]] = None
    confidence_summary: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None
    output_video_path: Optional[str] = None
    error_message: Optional[str] = None
    results: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, JobStatus) else str(self.status)
        return d

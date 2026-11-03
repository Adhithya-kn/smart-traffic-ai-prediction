"""
traffic_system/computer_vision/schemas.py - Data Classes & Schemas for Vision Pipeline
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from traffic_system.core.time_utils import now_iso


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


VEHICLE_CLASSES = {
    "car": "Car",
    "motorcycle": "Motorcycle",
    "bus": "Bus",
    "truck": "Truck"
}


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
    status: JobStatus = JobStatus.PENDING
    progress_pct: float = 0.0
    total_frames: int = 0
    processed_frames: int = 0
    duration_seconds: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    created_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None
    output_video_path: Optional[str] = None
    error_message: Optional[str] = None
    results: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, JobStatus) else str(self.status)
        return d

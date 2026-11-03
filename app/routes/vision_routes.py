"""
app/routes/vision_routes.py - Vision API Endpoints & Request Handlers
Dispatches video upload, YOLO background processing, tracking results, and video playback.
"""

import json
import base64
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from traffic_system.core.time_utils import now_iso
from traffic_system.storage.video_storage import get_video_storage
from traffic_system.computer_vision.job_manager import get_job_manager
from traffic_system.computer_vision.schemas import JobStatus


class VisionRouteHandler:
    """Encapsulates HTTP request handling for Computer Vision endpoints."""
    def __init__(self):
        self.storage = get_video_storage()
        self.job_manager = get_job_manager()

    def handle_upload(self, raw_bytes: bytes, filename: str = "sample_traffic.mp4") -> Tuple[int, Dict[str, Any]]:
        """Handles video upload payload."""
        ok, msg, meta = self.storage.save_upload(raw_bytes, filename)
        if not ok:
            return 400, {
                "success": False,
                "status": "error",
                "message": msg,
                "timestamp": now_iso()
            }
        return 200, {
            "success": True,
            "status": "success",
            "message": msg,
            "timestamp": now_iso(),
            "data": meta
        }

    def handle_process(self, body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """Submits video for background computer vision analysis."""
        video_id = body.get("video_id") or ""
        filename = body.get("filename") or "traffic_sample.mp4"

        if not video_id:
            return 400, {
                "success": False,
                "status": "error",
                "message": "Field 'video_id' is required to start processing.",
                "timestamp": now_iso()
            }

        video_path = self.storage.get_raw_video_path(video_id)
        if not video_path:
            return 404, {
                "success": False,
                "status": "error",
                "message": f"Video with ID '{video_id}' not found.",
                "timestamp": now_iso()
            }

        job = self.job_manager.submit_job(video_id, filename)
        return 200, {
            "success": True,
            "status": "success",
            "message": "Video analysis job dispatched successfully.",
            "timestamp": now_iso(),
            "data": {
                "job_id": job.job_id,
                "video_id": job.video_id,
                "status": job.status.value,
                "progress_pct": job.progress_pct
            }
        }

    def handle_get_job(self, job_id: str) -> Tuple[int, Dict[str, Any]]:
        """Returns progress and status of a processing job."""
        job = self.job_manager.get_job(job_id)
        if not job:
            return 404, {
                "success": False,
                "status": "error",
                "message": f"Job '{job_id}' not found.",
                "timestamp": now_iso()
            }

        return 200, {
            "success": True,
            "status": "success",
            "message": f"Job status is {job.status.value}",
            "timestamp": now_iso(),
            "data": job.to_dict()
        }

    def handle_get_results(self, job_id: str) -> Tuple[int, Dict[str, Any]]:
        """Returns structured detection, counting, and density metrics."""
        job = self.job_manager.get_job(job_id)
        if not job:
            return 404, {
                "success": False,
                "status": "error",
                "message": f"Job '{job_id}' not found.",
                "timestamp": now_iso()
            }

        if job.status == JobStatus.FAILED:
            return 400, {
                "success": False,
                "status": "error",
                "message": f"Job processing failed: {job.error_message}",
                "timestamp": now_iso()
            }

        if job.status != JobStatus.COMPLETED:
            return 202, {
                "success": True,
                "status": "processing",
                "message": f"Job is currently {job.status.value} ({job.progress_pct}%).",
                "timestamp": now_iso(),
                "data": {
                    "job_id": job.job_id,
                    "progress_pct": job.progress_pct,
                    "status": job.status.value
                }
            }

        return 200, {
            "success": True,
            "status": "success",
            "message": "Video analysis completed.",
            "timestamp": now_iso(),
            "data": job.results
        }

    def handle_get_video(self, job_id: str) -> Tuple[int, Optional[bytes], str]:
        """Streams annotated output video bytes."""
        video_path = self.storage.get_processed_video_path(job_id)
        if not video_path or not video_path.exists():
            return 404, None, "Video not found"

        content = video_path.read_bytes()
        return 200, content, "video/mp4"

    def handle_get_status(self) -> Tuple[int, Dict[str, Any]]:
        """Reports vision pipeline engine readiness and active jobs."""
        from traffic_system.computer_vision.detector import VehicleDetector
        temp_detector = VehicleDetector()
        return 200, {
            "success": True,
            "status": "success",
            "message": "Computer vision module operational.",
            "timestamp": now_iso(),
            "data": {
                "engine": "Sample-Video Vehicle Processing",
                "yolo_loaded": temp_detector.is_yolo_active,
                "yolo_model": temp_detector.model_name,
                "total_jobs_tracked": len(self.job_manager.jobs),
                "supported_formats": [".mp4", ".avi", ".mov", ".mkv"],
                "target_classes": ["car", "motorcycle", "bus", "truck"]
            }
        }


_VISION_HANDLER: Optional[VisionRouteHandler] = None

def get_vision_handler() -> VisionRouteHandler:
    global _VISION_HANDLER
    if _VISION_HANDLER is None:
        _VISION_HANDLER = VisionRouteHandler()
    return _VISION_HANDLER

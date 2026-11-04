"""
app/routes/vision_routes.py - Vision API Endpoints & Request Handlers
Dispatches video upload, genuine YOLO background processing, tracking results, live frame processing,
and closed-loop grid actuation with strict ownership validation and role-based access control.
"""

try:
    import torch
except ImportError:
    pass

import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from traffic_system.core.time_utils import now_iso
from traffic_system.storage.video_storage import get_video_storage
from traffic_system.computer_vision.job_manager import get_job_manager
from traffic_system.computer_vision.schemas import JobStatus
from traffic_system.computer_vision.detector import get_vehicle_detector, YOLOUnavailableError, YOLOInferenceError
from traffic_system.computer_vision.tracker import VehicleTracker
from traffic_system.computer_vision.density_estimator import TrafficDensityEstimator
from traffic_system.computer_vision.pcu_converter import IndoHCMPCUConverter
from traffic_system.computer_vision.incident_detector import IncidentDetector
from traffic_system.live.bridge import get_live_bridge
from traffic_system.core.entities import UserRole
from traffic_system.core.fs_utils import is_valid_identifier

logger = logging.getLogger("app.routes.vision_routes")


class VisionRouteHandler:
    """Encapsulates HTTP request handling for Computer Vision endpoints."""
    def __init__(self):
        self.storage = get_video_storage()
        self.job_manager = get_job_manager()
        self.live_tracker = VehicleTracker()
        self.live_density = TrafficDensityEstimator()
        self.live_incident = IncidentDetector()
        self._frame_counter = 0

    def _is_admin(self, user: Optional[Dict[str, Any]]) -> bool:
        if not user:
            return False
        role = user.get("role", "")
        return role in (UserRole.TRAFFIC_MANAGEMENT.value, "Traffic Authority", "Management")

    def handle_upload(
        self,
        raw_bytes: bytes,
        filename: str = "sample_traffic.mp4",
        owner: str = ""
    ) -> Tuple[int, Dict[str, Any]]:
        """Handles video upload payload, associating it with the owning user."""
        ok, msg, meta = self.storage.save_upload(raw_bytes, filename, owner=owner)
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

    def handle_upload_init(
        self,
        body: Dict[str, Any],
        requesting_user: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """Initializes a disk-backed chunked upload session for large video files."""
        if not isinstance(body, dict):
            return 400, {
                "success": False,
                "status": "error",
                "message": "Request body must be a JSON object.",
                "timestamp": now_iso()
            }

        filename = body.get("filename") or "traffic_sample.mp4"
        file_size = body.get("file_size")
        total_chunks = body.get("total_chunks")
        chunk_size = body.get("chunk_size", 8 * 1024 * 1024)
        expected_sha256 = body.get("sha256", "")

        if file_size is None or not isinstance(file_size, int) or file_size <= 0:
            return 400, {
                "success": False,
                "status": "error",
                "message": "Valid positive integer 'file_size' (in bytes) is required.",
                "timestamp": now_iso()
            }

        if total_chunks is None or not isinstance(total_chunks, int) or total_chunks <= 0:
            return 400, {
                "success": False,
                "status": "error",
                "message": "Valid positive integer 'total_chunks' is required.",
                "timestamp": now_iso()
            }

        owner = (requesting_user.get("username") if requesting_user else "") or "anonymous"
        ok, msg, meta = self.storage.init_chunked_upload(
            original_filename=filename,
            file_size=file_size,
            total_chunks=total_chunks,
            chunk_size=chunk_size,
            expected_sha256=expected_sha256,
            owner=owner
        )
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

    def handle_upload_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        stream,
        chunk_len: int,
        requesting_user: Optional[Dict[str, Any]] = None,
        chunk_sha256: str = ""
    ) -> Tuple[int, Dict[str, Any]]:
        """Streams a single upload chunk directly into disk-backed storage."""
        owner = requesting_user.get("username", "") if requesting_user else ""
        ok, msg, meta = self.storage.save_chunk_stream(
            upload_id=upload_id,
            chunk_index=chunk_index,
            stream=stream,
            chunk_bytes_len=chunk_len,
            requesting_owner=owner,
            chunk_sha256=chunk_sha256
        )
        if not ok:
            status_code = 403 if "Forbidden" in msg else 404 if "not found" in msg.lower() else 400
            return status_code, {
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

    def handle_upload_status(
        self,
        upload_id: str,
        requesting_user: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """Checks progress and missing chunks for an ongoing upload session."""
        owner = requesting_user.get("username", "") if requesting_user else ""
        ok, msg, meta = self.storage.get_chunked_upload_status(upload_id, requesting_owner=owner)
        if not ok:
            status_code = 403 if "Forbidden" in msg else 404 if "not found" in msg.lower() else 400
            return status_code, {
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

    def handle_upload_complete(
        self,
        body: Dict[str, Any],
        requesting_user: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """Finalizes chunked upload, assembles video on disk, and verifies SHA-256 and container."""
        if not isinstance(body, dict):
            return 400, {
                "success": False,
                "status": "error",
                "message": "Request body must be a JSON object.",
                "timestamp": now_iso()
            }

        upload_id = body.get("upload_id") or ""
        expected_sha256 = body.get("sha256") or ""
        if not upload_id:
            return 400, {
                "success": False,
                "status": "error",
                "message": "Field 'upload_id' is required to finalize upload.",
                "timestamp": now_iso()
            }

        owner = requesting_user.get("username", "") if requesting_user else ""
        ok, msg, meta = self.storage.finalize_chunked_upload(
            upload_id=upload_id,
            requesting_owner=owner,
            expected_sha256=expected_sha256
        )
        if not ok:
            status_code = 403 if "Forbidden" in msg else 404 if "not found" in msg.lower() else 400
            return status_code, {
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

    def handle_upload_stream(
        self,
        stream,
        length: int,
        filename: str = "sample_traffic.mp4",
        owner: str = ""
    ) -> Tuple[int, Dict[str, Any]]:
        """Handles video upload streaming directly to disk without reading entire file in memory."""
        ok, msg, meta = self.storage.save_upload_stream(stream, length, filename, owner=owner)
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

    def handle_process(
        self,
        body: Dict[str, Any],
        requesting_user: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """Submits video for background computer vision analysis with user ownership check."""
        if not isinstance(body, dict):
            return 400, {
                "success": False,
                "status": "error",
                "message": "Request body must be a valid JSON object.",
                "timestamp": now_iso()
            }

        video_id = body.get("video_id") or ""
        filename = body.get("filename") or "traffic_sample.mp4"
        simulation_mode = bool(body.get("simulation_mode", False))

        if not video_id:
            return 400, {
                "success": False,
                "status": "error",
                "message": "Field 'video_id' is required to start processing.",
                "timestamp": now_iso()
            }

        if not is_valid_identifier(video_id):
            return 400, {
                "success": False,
                "status": "error",
                "message": f"Invalid format for 'video_id': '{video_id}'. Only alphanumeric characters, dashes, and underscores allowed.",
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

        # Check ownership: prevent processing another user's video unless admin
        owner = self.storage.get_video_owner(video_id)
        if requesting_user:
            req_username = requesting_user.get("username", "")
            if owner and owner not in (req_username, "anonymous") and not self._is_admin(requesting_user):
                return 403, {
                    "success": False,
                    "status": "forbidden",
                    "message": "Forbidden: You do not have permission to process another user's video.",
                    "timestamp": now_iso()
                }
            job_owner = req_username
        else:
            job_owner = owner or ""

        job = self.job_manager.submit_job(
            video_id,
            filename,
            simulation_mode=simulation_mode,
            owner=job_owner
        )
        return 200, {
            "success": True,
            "status": "success",
            "message": "Video analysis job dispatched successfully.",
            "timestamp": now_iso(),
            "data": {
                "job_id": job.job_id,
                "video_id": job.video_id,
                "status": job.status.value,
                "progress_pct": job.progress_pct,
                "simulation_mode": simulation_mode,
                "owner": job.owner
            }
        }

    def handle_get_job(
        self,
        job_id: str,
        requesting_user: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """Returns progress and status of a processing job, enforcing owner boundary."""
        if not is_valid_identifier(job_id):
            return 400, {
                "success": False,
                "status": "error",
                "message": f"Invalid format for 'job_id': '{job_id}'.",
                "timestamp": now_iso()
            }

        job = self.job_manager.get_job(job_id)
        if not job:
            return 404, {
                "success": False,
                "status": "error",
                "message": f"Job '{job_id}' not found.",
                "timestamp": now_iso()
            }

        # Enforce owner boundary
        if requesting_user:
            req_username = requesting_user.get("username", "")
            if job.owner and job.owner != req_username and not self._is_admin(requesting_user):
                return 403, {
                    "success": False,
                    "status": "forbidden",
                    "message": "Forbidden: Access to this job is restricted to its owner.",
                    "timestamp": now_iso()
                }

        return 200, {
            "success": True,
            "status": "success",
            "message": f"Job status is {job.status.value}",
            "timestamp": now_iso(),
            "data": job.to_dict()
        }

    def handle_get_results(
        self,
        job_id: str,
        requesting_user: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """Returns structured detection, counting, PCU, and density metrics."""
        if not is_valid_identifier(job_id):
            return 400, {
                "success": False,
                "status": "error",
                "message": f"Invalid format for 'job_id': '{job_id}'.",
                "timestamp": now_iso()
            }

        job = self.job_manager.get_job(job_id)
        if not job:
            return 404, {
                "success": False,
                "status": "error",
                "message": f"Job '{job_id}' not found.",
                "timestamp": now_iso()
            }

        # Enforce owner boundary
        if requesting_user:
            req_username = requesting_user.get("username", "")
            if job.owner and job.owner != req_username and not self._is_admin(requesting_user):
                return 403, {
                    "success": False,
                    "status": "forbidden",
                    "message": "Forbidden: Access to these results is restricted to the job owner.",
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

    def handle_get_video(
        self,
        job_id: str,
        requesting_user: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Optional[Path], str]:
        """Resolves annotated output video path for chunked streaming, enforcing owner boundary."""
        if not is_valid_identifier(job_id):
            return 400, None, "Invalid format for 'job_id'."

        job = self.job_manager.get_job(job_id)
        if job and job.owner and job.owner != "anonymous":
            if not requesting_user:
                return 401, None, "Authentication required to stream this video."
            req_username = requesting_user.get("username", "")
            if job.owner != req_username and not self._is_admin(requesting_user):
                return 403, None, "Forbidden: Video streaming restricted to the job owner."

        video_path = self.storage.get_processed_video_path(job_id)
        if not video_path or not video_path.exists():
            return 404, None, "Video not found"
        return 200, video_path, "video/mp4"

    def handle_get_status(self) -> Tuple[int, Dict[str, Any]]:
        """Reports vision pipeline engine readiness and active jobs without reloading model weights."""
        detector = get_vehicle_detector()
        return 200, {
            "success": True,
            "status": "success",
            "message": "Computer vision module operational." if detector.is_yolo_active else "YOLO model unavailable for inference.",
            "timestamp": now_iso(),
            "data": {
                "engine": f"Ultralytics YOLO ({detector.model_name})" if detector.is_yolo_active else "Unavailable",
                "yolo_loaded": detector.is_yolo_active,
                "yolo_model": detector.model_name,
                "load_error": detector.load_error,
                "total_jobs_tracked": len(self.job_manager.jobs),
                "supported_formats": [".mp4", ".webm", ".avi", ".mov", ".mkv"],
                "target_classes": ["car", "motorcycle", "bus", "truck"]
            }
        }

    def handle_process_live_frame(
        self,
        body: Dict[str, Any],
        requesting_user: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Processes a single live camera frame sent from the browser client or CCTV feed.
        Decodes incoming base64 frame, applies real YOLO inference, ByteTrack kinematics,
        and Indo-HCM PCU flow normalization.
        """
        self._frame_counter += 1
        detector = get_vehicle_detector()

        if not detector.is_yolo_active:
            return 503, {
                "success": False,
                "status": "unavailable",
                "message": f"YOLO model is unavailable for live frame inference: {detector.load_error or 'Weights not loaded'}",
                "timestamp": now_iso()
            }

        if not isinstance(body, dict):
            return 400, {
                "success": False,
                "status": "error",
                "message": "Request body must be a JSON object.",
                "timestamp": now_iso()
            }

        frame_img = None
        img_payload = body.get("image") or body.get("frame") or body.get("image_data")
        frame_w, frame_h = 1280, 720
        if img_payload and isinstance(img_payload, str) and HAS_CV2:
            try:
                if "," in img_payload:
                    img_payload = img_payload.split(",", 1)[1]
                raw_bytes = base64.b64decode(img_payload)
                nparr = np.frombuffer(raw_bytes, np.uint8)
                frame_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame_img is not None:
                    frame_h, frame_w = frame_img.shape[:2]
            except Exception as e:
                logger.debug("Live frame decode error: %s", e)
                frame_img = None

        if frame_img is None:
            return 400, {
                "success": False,
                "status": "error",
                "message": "Invalid or unreadable video frame payload.",
                "timestamp": now_iso()
            }

        try:
            detections = detector.detect_frame(frame_img, frame_idx=self._frame_counter)
        except Exception as e:
            return 500, {
                "success": False,
                "status": "error",
                "message": f"YOLO inference error: {str(e)}",
                "timestamp": now_iso()
            }

        tracked = self.live_tracker.update(detections, frame_idx=self._frame_counter, fps=30.0)
        density = self.live_density.estimate(tracked, frame_w, frame_h)

        class_counts = {"car": 0, "motorcycle": 0, "bus": 0, "truck": 0, "pedestrian": 0, "bicycle": 0}
        speeds = []
        new_incidents = []

        for d in tracked:
            cname = (d.class_name or "").lower()
            if cname in class_counts:
                class_counts[cname] += 1
            else:
                class_counts[cname] = 1

            if d.speed_kmh > 0:
                speeds.append(d.speed_kmh)

            inc = self.live_incident.update(d.track_id or 0, d, d.speed_kmh, self._frame_counter)
            new_incidents.extend(inc)

        total_pcu = IndoHCMPCUConverter.calculate_total_pcu(class_counts)
        mean_speed = round(sum(speeds) / max(len(speeds), 1), 1) if speeds else 0.0

        return 200, {
            "success": True,
            "status": "success",
            "frame_idx": self._frame_counter,
            "data": {
                "detections": [d.to_dict() for d in tracked],
                "active_vehicle_count": len(tracked),
                "resolution": f"{frame_w}x{frame_h}",
                "density": density,
                "class_counts": class_counts,
                "total_pcu": total_pcu,
                "mean_speed_kmh": mean_speed,
                "new_incidents": new_incidents,
                "engine": f"Ultralytics YOLO ({detector.model_name})",
                "provenance": "GENUINE_YOLO_INFERENCE",
                "is_simulation": False
            }
        }

    def handle_actuate_live_grid(
        self,
        body: Dict[str, Any],
        requesting_user: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Closed-loop actuation: Injects vision metrics directly into the Bengaluru Live Grid.
        Strictly requires Traffic Management administrator role.
        """
        if not self._is_admin(requesting_user):
            return 403, {
                "success": False,
                "status": "forbidden",
                "message": "Forbidden: Administrative role (Traffic Management) required for live grid actuation.",
                "timestamp": now_iso()
            }

        if not isinstance(body, dict):
            return 400, {
                "success": False,
                "status": "error",
                "message": "Request body must be a JSON object.",
                "timestamp": now_iso()
            }

        corridor_id = body.get("corridor_id") or "RD_BLR_04"
        vision_metrics = body.get("vision_metrics") or {}

        bridge = get_live_bridge()
        actuation_result = bridge.inject_vision_telemetry(corridor_id, vision_metrics)

        return 200, {
            "success": True,
            "status": "success",
            "message": "Vision telemetry actuated into Live Grid.",
            "data": actuation_result
        }


_VISION_HANDLER: Optional[VisionRouteHandler] = None

def get_vision_handler() -> VisionRouteHandler:
    global _VISION_HANDLER
    if _VISION_HANDLER is None:
        _VISION_HANDLER = VisionRouteHandler()
    return _VISION_HANDLER

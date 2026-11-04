"""
traffic_system/computer_vision/job_manager.py - Asynchronous Video Processing Job Manager
Dispatches background video analysis jobs with queue capacity limits, execution timeouts,
durable atomic job persistence across restarts, and stale artifact cleanup.
"""

import os
import time
import uuid
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, Optional, List

from traffic_system.config import (
    ARTIFACTS_DIR,
    CV_JOB_TIMEOUT_SECONDS,
    JOBS_DB_PATH
)
from traffic_system.core.time_utils import now_iso
from traffic_system.core.fs_utils import atomic_json_dump, safe_read_json, is_valid_identifier
from traffic_system.storage.video_storage import get_video_storage
from traffic_system.computer_vision.schemas import VisionJob, JobStatus
from traffic_system.computer_vision.video_processor import VideoProcessor, OutputVerificationError
from traffic_system.storage.migrations import migrate_jobs_data

logger = logging.getLogger("traffic_system.computer_vision.job_manager")

JOBS_PERSISTENCE_FILE = Path(JOBS_DB_PATH)
MAX_QUEUE_CAPACITY = 20


class VisionJobManager:
    """
    Manages asynchronous lifecycle of video analysis background workers.
    Enforces queue limits, execution timeouts, persistent job metadata,
    and automatic cleanup.
    """
    _instance: Optional["VisionJobManager"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        max_workers: int = 2,
        max_queue_size: int = MAX_QUEUE_CAPACITY,
        timeout_seconds: float = CV_JOB_TIMEOUT_SECONDS
    ):
        self.jobs: Dict[str, VisionJob] = {}
        self.max_queue_size = max_queue_size
        self.timeout_seconds = timeout_seconds
        self.storage = get_video_storage()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="CV-Worker")
        self._jobs_lock = threading.RLock()
        self._load_persisted_jobs()

    @classmethod
    def get_instance(cls) -> "VisionJobManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = VisionJobManager()
            return cls._instance

    def _load_persisted_jobs(self) -> None:
        """Loads persisted jobs from disk upon initialization with automatic schema migration."""
        with self._jobs_lock:
            if not JOBS_PERSISTENCE_FILE.exists():
                return
            raw_data = safe_read_json(JOBS_PERSISTENCE_FILE)
            if isinstance(raw_data, dict):
                migrated_data, was_modified = migrate_jobs_data(raw_data)
                for j_id, j_dict in migrated_data.items():
                    if isinstance(j_dict, dict) and is_valid_identifier(j_id):
                        try:
                            # Reconstruct VisionJob
                            job = VisionJob(
                                job_id=j_dict.get("job_id", j_id),
                                video_id=j_dict.get("video_id", ""),
                                original_filename=j_dict.get("original_filename", ""),
                                owner=j_dict.get("owner", "anonymous"),
                                status=JobStatus(j_dict.get("status", "FAILED")),
                                progress_pct=j_dict.get("progress_pct", 0.0),
                                total_frames=j_dict.get("total_frames", 0),
                                processed_frames=j_dict.get("processed_frames", 0),
                                duration_seconds=j_dict.get("duration_seconds", 0.0),
                                fps=j_dict.get("fps", 0.0),
                                width=j_dict.get("width", 0),
                                height=j_dict.get("height", 0),
                                model_name=j_dict.get("model_name", "yolo11n.pt"),
                                model_status=j_dict.get("model_status", "active"),
                                provenance=j_dict.get("provenance", "Genuine YOLO inference"),
                                camera_config=j_dict.get("camera_config"),
                                confidence_summary=j_dict.get("confidence_summary"),
                                created_at=j_dict.get("created_at", now_iso()),
                                completed_at=j_dict.get("completed_at"),
                                output_video_path=j_dict.get("output_video_path"),
                                error_message=j_dict.get("error_message"),
                                results=j_dict.get("results")
                            )
                            # If server restarted during processing, mark interrupted job
                            if job.status == JobStatus.PROCESSING:
                                job.status = JobStatus.FAILED
                                job.error_message = "Server restarted during job processing."
                                was_modified = True
                            self.jobs[j_id] = job
                        except Exception:
                            continue
                if was_modified:
                    self._save_persisted_jobs()

    def _save_persisted_jobs(self) -> None:
        """Atomically persists active job states to disk."""
        with self._jobs_lock:
            serialized = {j_id: job.to_dict() for j_id, job in self.jobs.items()}
            try:
                atomic_json_dump(serialized, JOBS_PERSISTENCE_FILE)
            except Exception as e:
                logger.error("Failed to persist vision jobs to disk: %s", e)

    def submit_job(
        self,
        video_id: str,
        original_filename: str,
        simulation_mode: bool = False,
        owner: str = "",
        camera_config: Optional[Dict[str, Any]] = None
    ) -> VisionJob:
        """
        Schedules a new background video processing job with queue limits and user ownership.
        Raises RuntimeError if the queue capacity limit is exceeded.
        """
        if not is_valid_identifier(video_id):
            raise ValueError(f"Invalid video_id identifier: '{video_id}'")

        with self._jobs_lock:
            active_jobs = sum(1 for j in self.jobs.values() if j.status in (JobStatus.PENDING, JobStatus.PROCESSING))
            if active_jobs >= self.max_queue_size:
                raise RuntimeError(
                    f"Video processing queue is at capacity ({active_jobs}/{self.max_queue_size} active jobs). "
                    f"Please wait for existing jobs to complete."
                )

            job_id = f"cv_{uuid.uuid4().hex[:10]}"
            job = VisionJob(
                job_id=job_id,
                video_id=video_id,
                original_filename=original_filename,
                owner=owner,
                status=JobStatus.PENDING,
                progress_pct=0.0,
                camera_config=camera_config
            )
            self.jobs[job_id] = job
            self._save_persisted_jobs()

        self._executor.submit(self._run_job, job_id, video_id, simulation_mode, camera_config)
        return job

    def _run_job(
        self,
        job_id: str,
        video_id: str,
        simulation_mode: bool = False,
        camera_config: Optional[Dict[str, Any]] = None
    ) -> None:
        start_wall_time = time.time()
        with self._jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            job.status = JobStatus.PROCESSING
            self._save_persisted_jobs()

        temp_output_path = None
        final_output_path = None
        try:
            input_path = self.storage.get_raw_video_path(video_id)
            if not input_path or not input_path.exists():
                raise FileNotFoundError(f"Video file with ID '{video_id}' not found.")

            temp_output_path = self.storage.create_temp_processed_path(job_id)
            final_output_path = self.storage.create_processed_path(job_id)

            # Thread-local VideoProcessor instance to eliminate race conditions
            processor = VideoProcessor(simulation_mode=simulation_mode, camera_config=camera_config)

            def on_progress(frac: float, processed: int, total: int):
                # Check execution timeout
                elapsed = time.time() - start_wall_time
                if elapsed > self.timeout_seconds:
                    raise TimeoutError(f"Job processing exceeded maximum allowed timeout of {self.timeout_seconds:.0f}s.")

                with self._jobs_lock:
                    job.progress_pct = round(frac * 100.0, 1)
                    job.processed_frames = processed
                    job.total_frames = total

            results = processor.process_video(
                input_path=input_path,
                output_path=temp_output_path,
                progress_callback=on_progress
            )

            # Pre-commit output verification
            if not temp_output_path.exists():
                raise OutputVerificationError("Temporary processed video file was not created.")

            VideoProcessor.verify_output_video(temp_output_path, expected_min_frames=1)

            # Two-Phase Commit: Atomically replace temporary file to final path
            os.replace(str(temp_output_path), str(final_output_path))

            # Post-commit verification of final output path
            VideoProcessor.verify_output_video(final_output_path, expected_min_frames=1)

            with self._jobs_lock:
                job.status = JobStatus.COMPLETED
                job.progress_pct = 100.0
                job.completed_at = now_iso()
                job.output_video_path = str(final_output_path)
                job.results = results
                job.provenance = results.get("provenance", "Genuine YOLO inference")
                job.model_name = results.get("engine", "yolo11n.pt")
                job.confidence_summary = results.get("confidence_summary")

                if "source_video" in results:
                    src = results["source_video"]
                    job.total_frames = src.get("total_frames_analyzed", job.total_frames)
                    job.processed_frames = job.total_frames
                    job.fps = src.get("fps", 0.0)
                    job.duration_seconds = src.get("video_duration_seconds", 0.0)
                    res_str = src.get("resolution", "")
                    if "x" in res_str:
                        parts = res_str.split("x", 1)
                        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                            job.width = int(parts[0])
                            job.height = int(parts[1])

                self._save_persisted_jobs()

        except Exception as e:
            logger.error("Job %s execution failed: %s", job_id, e, exc_info=True)
            if temp_output_path and temp_output_path.exists():
                try:
                    temp_output_path.unlink()
                except OSError:
                    pass
            if final_output_path and final_output_path.exists():
                try:
                    final_output_path.unlink()
                except OSError:
                    pass
            with self._jobs_lock:
                job.status = JobStatus.FAILED
                job.error_message = f"Video processing error: {str(e)}"
                job.completed_at = now_iso()
                self._save_persisted_jobs()

    def get_job(self, job_id: str) -> Optional[VisionJob]:
        if not is_valid_identifier(job_id):
            return None
        with self._jobs_lock:
            return self.jobs.get(job_id)

    def get_job_owner(self, job_id: str) -> Optional[str]:
        if not is_valid_identifier(job_id):
            return None
        with self._jobs_lock:
            job = self.jobs.get(job_id)
            return job.owner if job else None

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._jobs_lock:
            return [j.to_dict() for j in self.jobs.values()]

    def delete_job(self, job_id: str) -> bool:
        """Deletes job metadata, processed artifacts, and temporary files."""
        if not is_valid_identifier(job_id):
            return False

        with self._jobs_lock:
            job = self.jobs.pop(job_id, None)
            if not job:
                return False

            # Delete processed output file if present
            proc_path = self.storage.get_processed_video_path(job_id)
            if proc_path and proc_path.exists():
                try:
                    proc_path.unlink()
                except OSError:
                    pass

            # Delete temporary files
            temp_path = self.storage.create_temp_processed_path(job_id)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

            self._save_persisted_jobs()
            return True

    def cleanup_stale_jobs(self, max_age_hours: float = 24.0, max_age_seconds: Optional[float] = None) -> int:
        """Prunes completed or failed jobs older than max_age_hours or max_age_seconds."""
        now = time.time()
        if max_age_seconds is not None:
            max_age_sec = float(max_age_seconds)
        else:
            max_age_sec = max_age_hours * 3600.0
        removed_count = 0

        with self._jobs_lock:
            to_remove = []
            for j_id, job in self.jobs.items():
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    # Check age
                    try:
                        from datetime import datetime
                        created_dt = datetime.fromisoformat(job.created_at)
                        age = now - created_dt.timestamp()
                        if age > max_age_sec:
                            to_remove.append(j_id)
                    except Exception:
                        pass

            for j_id in to_remove:
                if self.delete_job(j_id):
                    removed_count += 1

        return removed_count


_JOB_MANAGER: Optional[VisionJobManager] = None

def get_job_manager() -> VisionJobManager:
    global _JOB_MANAGER
    if _JOB_MANAGER is None:
        _JOB_MANAGER = VisionJobManager.get_instance()
    return _JOB_MANAGER

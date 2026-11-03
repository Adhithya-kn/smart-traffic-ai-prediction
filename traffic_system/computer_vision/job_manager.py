"""
traffic_system/computer_vision/job_manager.py - Asynchronous Video Processing Job Manager
Dispatches background video analysis jobs, monitors progress, and manages lifecycle.
"""

import uuid
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, Optional, List

from traffic_system.core.time_utils import now_iso
from traffic_system.storage.video_storage import get_video_storage
from traffic_system.computer_vision.schemas import VisionJob, JobStatus
from traffic_system.computer_vision.video_processor import VideoProcessor

logger = logging.getLogger("traffic_system.computer_vision.job_manager")


class VisionJobManager:
    """Manages asynchronous lifecycle of video analysis background workers."""
    _instance: Optional["VisionJobManager"] = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 2):
        self.jobs: Dict[str, VisionJob] = {}
        self.storage = get_video_storage()
        self.processor = VideoProcessor()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="CV-Worker")
        self._jobs_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> "VisionJobManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = VisionJobManager()
            return cls._instance

    def submit_job(self, video_id: str, original_filename: str) -> VisionJob:
        """Schedules a new background video processing job."""
        job_id = f"cv_{uuid.uuid4().hex[:10]}"
        job = VisionJob(
            job_id=job_id,
            video_id=video_id,
            original_filename=original_filename,
            status=JobStatus.PENDING,
            progress_pct=0.0
        )

        with self._jobs_lock:
            self.jobs[job_id] = job

        self._executor.submit(self._run_job, job_id, video_id)
        return job

    def _run_job(self, job_id: str, video_id: str) -> None:
        with self._jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            job.status = JobStatus.PROCESSING

        input_path = self.storage.get_raw_video_path(video_id)
        if not input_path or not input_path.exists():
            with self._jobs_lock:
                job.status = JobStatus.FAILED
                job.error_message = f"Video file with ID '{video_id}' not found."
                job.completed_at = now_iso()
            return

        output_path = self.storage.create_processed_path(job_id)

        def on_progress(frac: float, processed: int, total: int):
            with self._jobs_lock:
                job.progress_pct = round(frac * 100.0, 1)
                job.processed_frames = processed
                job.total_frames = total

        try:
            results = self.processor.process_video(
                input_path=input_path,
                output_path=output_path,
                progress_callback=on_progress
            )
            with self._jobs_lock:
                job.status = JobStatus.COMPLETED
                job.progress_pct = 100.0
                job.completed_at = now_iso()
                job.output_video_path = str(output_path)
                job.results = results
        except Exception as e:
            logger.error("Job %s execution failed: %s", job_id, e, exc_info=True)
            with self._jobs_lock:
                job.status = JobStatus.FAILED
                job.error_message = f"Video processing error: {str(e)}"
                job.completed_at = now_iso()

    def get_job(self, job_id: str) -> Optional[VisionJob]:
        with self._jobs_lock:
            return self.jobs.get(job_id)

    def list_jobs(self) -> List[VisionJob]:
        with self._jobs_lock:
            return list(self.jobs.values())


def get_job_manager() -> VisionJobManager:
    return VisionJobManager.get_instance()

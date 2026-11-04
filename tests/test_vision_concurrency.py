"""
tests/test_vision_concurrency.py - Concurrency & Race Condition Verification
Asserts that concurrent background processing jobs maintain thread-local isolation
without wiping each other's tracker IDs or vehicle counts.
"""

import time
import tempfile
import cv2
from pathlib import Path
import pytest
from traffic_system.computer_vision.job_manager import VisionJobManager
from traffic_system.computer_vision.schemas import JobStatus
from traffic_system.storage.video_storage import get_video_storage


def test_concurrent_jobs_isolation(tmp_path):
    storage = get_video_storage()

    sample_file = Path("app/static/sample_traffic.mp4")
    assert sample_file.exists(), "Sample traffic video must exist."

    # Extract 12 real traffic frames for lightning-fast deterministic concurrency testing
    cap = cv2.VideoCapture(str(sample_file))
    frames = []
    for _ in range(12):
        ret, frame = cap.read()
        if ret and frame is not None:
            frames.append(frame)
    cap.release()

    assert len(frames) >= 5, "Could not extract sample frames for concurrency test."
    h, w = frames[0].shape[:2]

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        short_clip_path = Path(tf.name)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(short_clip_path), fourcc, 30.0, (w, h))
    for f in frames:
        out.write(f)
    out.release()

    try:
        sample_bytes = short_clip_path.read_bytes()

        ok1, _, meta1 = storage.save_upload(sample_bytes, "concurrent_a.mp4")
        ok2, _, meta2 = storage.save_upload(sample_bytes, "concurrent_b.mp4")
        assert ok1 and ok2

        manager = VisionJobManager(max_workers=2)

        # Submit both jobs concurrently
        job1 = manager.submit_job(meta1["video_id"], "concurrent_a.mp4")
        job2 = manager.submit_job(meta2["video_id"], "concurrent_b.mp4")

        assert job1.job_id != job2.job_id

        # Wait for completion (fast 12-frame clips complete in < 3s)
        start_wait = time.time()
        while time.time() - start_wait < 30.0:
            j1 = manager.get_job(job1.job_id)
            j2 = manager.get_job(job2.job_id)
            if j1.status in (JobStatus.COMPLETED, JobStatus.FAILED) and j2.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            time.sleep(0.2)

        assert j1.status == JobStatus.COMPLETED
        assert j2.status == JobStatus.COMPLETED

        # Verify both jobs have independent telemetry and results
        assert "pcu_telemetry" in j1.results
        assert "pcu_telemetry" in j2.results
        assert j1.results["total_unique_vehicles"] > 0
        assert j2.results["total_unique_vehicles"] > 0
        assert j1.results["is_simulation"] is False
        assert j2.results["is_simulation"] is False

        # Output video files must both exist independently
        assert Path(j1.output_video_path).exists()
        assert Path(j2.output_video_path).exists()
        assert j1.output_video_path != j2.output_video_path
    finally:
        short_clip_path.unlink(missing_ok=True)


def test_bounded_job_queue_capacity():
    """Confirms that job submission enforces max_queue_size limits."""
    from traffic_system.computer_vision.schemas import VisionJob
    mgr = VisionJobManager(max_workers=1, max_queue_size=2)

    with mgr._jobs_lock:
        mgr.jobs["queued_1"] = VisionJob("queued_1", "vid_1", "f1.mp4", status=JobStatus.PENDING)
        mgr.jobs["queued_2"] = VisionJob("queued_2", "vid_2", "f2.mp4", status=JobStatus.PROCESSING)

    with pytest.raises(RuntimeError) as exc_info:
        mgr.submit_job(video_id="vid_3", original_filename="f3.mp4")
    assert "queue is at capacity" in str(exc_info.value).lower()


def test_job_processing_timeout_behavior(monkeypatch):
    """Verifies that jobs exceeding execution timeout are terminated with JobStatus.FAILED."""
    storage = get_video_storage()
    sample_file = Path("app/static/sample_traffic.mp4")
    ok, _, meta = storage.save_upload(sample_file.read_bytes(), "timeout_test.mp4")
    assert ok is True

    # Configure aggressive 0.4s timeout
    mgr = VisionJobManager(max_workers=1, timeout_seconds=0.4)

    # Simulate slow frame-by-frame processing that triggers timeout
    def mock_slow_process(self, in_p, out_p, progress_callback=None, **kwargs):
        time.sleep(0.6)
        if progress_callback:
            progress_callback(10.0)
        time.sleep(0.6)
        return {"status": "success"}

    from traffic_system.computer_vision.video_processor import VideoProcessor
    monkeypatch.setattr(VideoProcessor, "process_video", mock_slow_process)

    job = mgr.submit_job(meta["video_id"], "timeout_test.mp4")

    for _ in range(40):
        time.sleep(0.1)
        j = mgr.get_job(job.job_id)
        if j and j.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break

    final_job = mgr.get_job(job.job_id)
    assert final_job is not None
    assert final_job.status == JobStatus.FAILED
    assert "timeout" in str(final_job.error_message).lower()


"""
tests/test_job_manager.py - Unit Tests for Asynchronous Vision Job Manager
Validates failure boundaries on corrupt or missing video, and verifies genuine lifecycle on valid MP4.
"""

import time
from pathlib import Path
import pytest
from traffic_system.computer_vision.job_manager import VisionJobManager
from traffic_system.computer_vision.schemas import JobStatus
from traffic_system.storage.video_storage import get_video_storage
from traffic_system.computer_vision.video_processor import VideoProcessor


def test_job_manager_missing_video_failure():
    mgr = VisionJobManager(max_workers=1)
    job = mgr.submit_job(video_id="nonexistent_id_9999", original_filename="fake.mp4")

    # Give background worker thread a moment to process
    time.sleep(0.5)

    retrieved = mgr.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.status == JobStatus.FAILED
    assert "not found" in str(retrieved.error_message).lower()


def test_job_manager_corrupt_mp4_failure(tmp_path):
    storage = get_video_storage()
    # Upload corrupt binary garbage that OpenCV cannot open
    corrupt_content = b"\x00\x00\x00 ftypisom" + (b"\xff" * 2000)
    ok, _, meta = storage.save_upload(corrupt_content, "corrupt_sample.mp4")
    assert ok is True
    vid = meta["video_id"]

    mgr = VisionJobManager(max_workers=1)
    job = mgr.submit_job(video_id=vid, original_filename="corrupt_sample.mp4")

    for _ in range(40):
        time.sleep(0.1)
        j = mgr.get_job(job.job_id)
        if j and j.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break

    final_job = mgr.get_job(job.job_id)
    assert final_job is not None
    assert final_job.status == JobStatus.FAILED
    assert "OpenCV could not open video file" in str(final_job.error_message)


def test_job_manager_successful_processing_lifecycle(tmp_path):
    storage = get_video_storage()
    sample_file = Path("app/static/sample_traffic.mp4")
    assert sample_file.exists(), "Sample traffic video must be present."
    sample_content = sample_file.read_bytes()

    ok, _, meta = storage.save_upload(sample_content, "lifecycle_sample.mp4")
    assert ok is True
    vid = meta["video_id"]

    mgr = VisionJobManager(max_workers=1)
    job = mgr.submit_job(video_id=vid, original_filename="lifecycle_sample.mp4")
    assert job.status in (JobStatus.PENDING, JobStatus.PROCESSING)

    # Wait for job completion (up to 30s to accommodate heavy test suite load)
    for _ in range(150):
        time.sleep(0.2)
        j = mgr.get_job(job.job_id)
        if j and j.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break

    final_job = mgr.get_job(job.job_id)
    assert final_job is not None
    assert final_job.status == JobStatus.COMPLETED
    assert final_job.progress_pct == 100.0
    assert final_job.results is not None
    assert "total_unique_vehicles" in final_job.results
    assert final_job.results["provenance"] == "Genuine YOLO inference"
    assert final_job.results["is_simulation"] is False
    assert final_job.results["processing_provenance"] == "GENUINE_YOLO_INFERENCE"

    # Verify that the final output exists, is non-empty, and can be opened
    out_path = Path(final_job.output_video_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0
    VideoProcessor.verify_output_video(out_path, expected_min_frames=1)


def test_job_manager_queue_limit_and_persistence(tmp_path):
    from traffic_system.computer_vision.schemas import VisionJob
    mgr = VisionJobManager(max_workers=1, max_queue_size=2)

    # Populate 2 active jobs directly in state to simulate full queue
    with mgr._jobs_lock:
        mgr.jobs["cv_test1"] = VisionJob("cv_test1", "vid1", "v1.mp4", status=JobStatus.PENDING)
        mgr.jobs["cv_test2"] = VisionJob("cv_test2", "vid2", "v2.mp4", status=JobStatus.PROCESSING)
        mgr._save_persisted_jobs()

    # Attempt 3rd job: should raise RuntimeError due to queue capacity
    with pytest.raises(RuntimeError) as exc:
        mgr.submit_job(video_id="fake_3", original_filename="v3.mp4")
    assert "queue is at capacity" in str(exc.value)

    # Test persistence reloading
    mgr2 = VisionJobManager(max_workers=1)
    assert mgr2.get_job("cv_test1") is not None

    # Mark completed and test job cleanup
    mgr.jobs["cv_test1"].status = JobStatus.COMPLETED
    mgr.jobs["cv_test2"].status = JobStatus.FAILED


def test_failed_output_cannot_become_completed_job(tmp_path, monkeypatch):
    """
    Verifies that when video processing fails or generates invalid output,
    the job is marked as FAILED and NEVER transitions to COMPLETED.
    """
    storage = get_video_storage()
    sample_file = Path("app/static/sample_traffic.mp4")
    assert sample_file.exists()
    ok, _, meta = storage.save_upload(sample_file.read_bytes(), "fail_sim.mp4")
    assert ok is True

    mgr = VisionJobManager(max_workers=1)

    # Simulate processor raising VideoProcessingError during rendering
    def mock_broken_process(*args, **kwargs):
        from traffic_system.computer_vision.video_processor import VideoProcessingError
        raise VideoProcessingError("Simulated encoder failure: broken pipeline")

    from traffic_system.computer_vision.video_processor import VideoProcessor
    monkeypatch.setattr(VideoProcessor, "process_video", mock_broken_process)

    job = mgr.submit_job(video_id=meta["video_id"], original_filename="fail_sim.mp4")
    for _ in range(40):
        time.sleep(0.1)
        j = mgr.get_job(job.job_id)
        if j and j.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break

    final_job = mgr.get_job(job.job_id)
    assert final_job is not None
    assert final_job.status == JobStatus.FAILED
    assert final_job.status != JobStatus.COMPLETED
    assert "Simulated encoder failure" in str(final_job.error_message)

    cleaned = mgr.cleanup_stale_jobs(max_age_seconds=0.0)
    assert cleaned >= 2

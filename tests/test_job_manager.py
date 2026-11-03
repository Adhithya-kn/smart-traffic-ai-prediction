"""
tests/test_job_manager.py - Unit Tests for Asynchronous Vision Job Manager
"""

import time
from traffic_system.computer_vision.job_manager import VisionJobManager
from traffic_system.computer_vision.schemas import JobStatus
from traffic_system.storage.video_storage import get_video_storage


def test_job_manager_missing_video_failure():
    mgr = VisionJobManager(max_workers=1)
    job = mgr.submit_job(video_id="nonexistent_id_9999", original_filename="fake.mp4")

    # Give background worker thread a moment to process
    time.sleep(0.5)

    retrieved = mgr.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.status == JobStatus.FAILED
    assert "not found" in str(retrieved.error_message).lower()


def test_job_manager_successful_processing_lifecycle(tmp_path):
    storage = get_video_storage()
    # Create fake sample video
    sample_content = b"\x00\x00\x00 ftypisom" + (b"\x00" * 2000)
    ok, _, meta = storage.save_upload(sample_content, "lifecycle_sample.mp4")
    assert ok is True
    vid = meta["video_id"]

    mgr = VisionJobManager(max_workers=1)
    job = mgr.submit_job(video_id=vid, original_filename="lifecycle_sample.mp4")
    assert job.status in (JobStatus.PENDING, JobStatus.PROCESSING)

    # Wait for job completion
    for _ in range(30):
        time.sleep(0.1)
        j = mgr.get_job(job.job_id)
        if j and j.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break

    final_job = mgr.get_job(job.job_id)
    assert final_job is not None
    assert final_job.status == JobStatus.COMPLETED
    assert final_job.progress_pct == 100.0
    assert final_job.results is not None
    assert "total_unique_vehicles" in final_job.results
    assert final_job.results["provenance"] == "Sample-video analysis"

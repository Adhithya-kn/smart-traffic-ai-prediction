"""
tests/test_north_east_chunked_upload_and_processing.py
Verifies end-to-end chunked upload and genuine YOLO processing of North-East.mp4
without Python interpreter crashes, symbol collision segfaults, or socket drops.
"""

import os
import time
import hashlib
import shutil
from pathlib import Path
import pytest

from traffic_system.config import BASE_DIR, JOBS_DB_PATH
from traffic_system.storage.video_storage import get_video_storage
from traffic_system.computer_vision.job_manager import get_job_manager
from traffic_system.computer_vision.schemas import JobStatus
from traffic_system.computer_vision.video_processor import VideoProcessor

# Large opt-in fixture: the real 55-174 MB Bengaluru video is gitignored, so the
# default/clean-clone test run must skip this test instead of failing.
_NORTH_EAST_VIDEO = BASE_DIR / "Dataset" / "North-East.mp4"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_HEAVY_VIDEO_TEST", "0").lower() not in ("1", "true", "yes"),
        reason=(
            "Heavy 55-174 MB video inference is opt-in. "
            "Set RUN_HEAVY_VIDEO_TEST=1 and select with -m integration."
        ),
    ),
    pytest.mark.skipif(
        not _NORTH_EAST_VIDEO.exists(),
        reason="Dataset/North-East.mp4 is absent (gitignored large video fixture).",
    ),
]


def _clean_storage():
    """Purges all transient video files while strictly preserving .gitkeep markers."""
    storage = get_video_storage()
    for folder in (storage.raw_dir, storage.chunks_dir, storage.processed_dir, storage.base_dir / "temp"):
        if folder.exists():
            for item in folder.iterdir():
                if item.name == ".gitkeep":
                    continue
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink(missing_ok=True)
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                except Exception:
                    pass
    with storage._lock:
        storage._metadata_cache.clear()

    # Reset job manager and persistence file. JOBS_DB_PATH is redirected to the
    # session temp root by tests/conftest.py, never the git-tracked artifact.
    job_mgr = get_job_manager()
    with job_mgr._jobs_lock:
        job_mgr.jobs.clear()
    jobs_file = Path(JOBS_DB_PATH)
    try:
        jobs_file.write_bytes(b"{}\n")
        os.chmod(jobs_file, 0o600)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def purge_test_storage():
    """
    Pytest fixture ensuring video storage and vision_jobs.json are clean before
    and after the integration test run, ensuring zero video storage footprint.
    """
    _clean_storage()
    try:
        yield
    finally:
        _clean_storage()


@pytest.mark.integration
def test_north_east_chunked_upload_and_inference():
    """Simulates 8 MB chunked upload of North-East.mp4 and executes genuine YOLO processing."""
    video_source = _NORTH_EAST_VIDEO
    assert video_source.exists(), f"Source video missing: {video_source}"

    file_size = video_source.stat().st_size
    chunk_size = 8 * 1024 * 1024
    total_chunks = (file_size + chunk_size - 1) // chunk_size

    # Calculate overall SHA-256
    h = hashlib.sha256()
    with open(video_source, "rb") as f:
        while block := f.read(65536):
            h.update(block)
    full_sha256 = h.hexdigest()

    storage = get_video_storage()
    # 1. Initialize chunked upload
    ok, msg, init_data = storage.init_chunked_upload(
        original_filename="North-East.mp4",
        file_size=file_size,
        total_chunks=total_chunks,
        chunk_size=chunk_size,
        expected_sha256=full_sha256,
        owner="traffic_admin"
    )
    assert ok, f"Init failed: {msg}"
    upload_id = init_data["upload_id"]

    # 2. Upload chunks
    with open(video_source, "rb") as f:
        for chunk_idx in range(total_chunks):
            chunk_bytes = f.read(chunk_size)
            import io
            c_stream = io.BytesIO(chunk_bytes)
            c_sha = hashlib.sha256(chunk_bytes).hexdigest()
            c_ok, c_msg, _ = storage.save_chunk_stream(
                upload_id=upload_id,
                chunk_index=chunk_idx,
                stream=c_stream,
                chunk_bytes_len=len(chunk_bytes),
                requesting_owner="traffic_admin",
                chunk_sha256=c_sha
            )
            assert c_ok, f"Chunk {chunk_idx} failed: {c_msg}"

    # 3. Finalize chunked upload
    fin_ok, fin_msg, fin_data = storage.finalize_chunked_upload(
        upload_id=upload_id,
        requesting_owner="traffic_admin",
        expected_sha256=full_sha256
    )
    assert fin_ok, f"Finalize failed: {fin_msg}"
    video_id = fin_data["video_id"]
    assert video_id, "video_id must not be empty"

    # Verify assembled video exists and matches source size
    raw_path = storage.get_raw_video_path(video_id)
    assert raw_path is not None and raw_path.exists()
    assert raw_path.stat().st_size == file_size

    # 4. Dispatch background job via JobManager
    job_mgr = get_job_manager()
    job = job_mgr.submit_job(
        video_id=video_id,
        original_filename="North-East.mp4",
        simulation_mode=False,
        owner="traffic_admin"
    )
    assert job.status in (JobStatus.PENDING, JobStatus.PROCESSING)

    # 5. Poll job status through thread-safe getter
    deadline = time.time() + 180.0
    completed = False
    while time.time() < deadline:
        job_dict = job_mgr.get_job_dict(job.job_id)
        assert job_dict is not None
        status = job_dict["status"]
        if status == JobStatus.COMPLETED.value:
            completed = True
            break
        elif status == JobStatus.FAILED.value:
            pytest.fail(f"Job failed with error: {job_dict.get('error_message')}")
        time.sleep(1.0)

    assert completed, "Job did not complete within timeout"

    # 6. Verify result integrity
    final_job = job_mgr.get_job_dict(job.job_id)
    results = final_job["results"]
    assert results is not None
    assert results["processing_provenance"] == "GENUINE_YOLO_INFERENCE"
    assert results["total_unique_vehicles"] > 0
    assert "class_counts" in results
    class_counts = results["class_counts"]
    for v_class in ("car", "motorcycle", "bicycle", "bus", "truck"):
        assert v_class in class_counts

    # Verify Route-to-Route Transition & Flow Metrics
    assert "route_flow" in results
    rf = results["route_flow"]
    assert rf["route_name"] == "Route A -> Route B"
    assert "transitions_count" in rf
    assert "transit_frequency_vpm" in rf
    assert "average_headway_sec" in rf
    assert "transitions_by_class" in rf

    # Verify annotated video output
    output_path = Path(final_job["output_video_path"])
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    VideoProcessor.verify_output_video(output_path, expected_min_frames=1)

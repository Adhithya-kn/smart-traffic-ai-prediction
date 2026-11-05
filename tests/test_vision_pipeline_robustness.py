"""
tests/test_vision_pipeline_robustness.py - Robustness Tests for Computer Vision Pipeline
Covers:
1. Empty frames
2. Corrupt MP4
3. Unavailable YOLO
4. Zero detections
5. Failed output generation & verification
"""

import os
import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest

from traffic_system.computer_vision.detector import (
    VehicleDetector,
    YOLOUnavailableError,
    YOLOInferenceError
)
from traffic_system.computer_vision.video_processor import (
    VideoProcessor,
    VideoProcessingError,
    OutputVerificationError
)
from traffic_system.computer_vision.job_manager import VisionJobManager
from traffic_system.computer_vision.schemas import JobStatus
from traffic_system.storage.video_storage import get_video_storage
from app.routes.vision_routes import VisionRouteHandler


# -----------------------------------------------------------------------------
# 1. Empty frames
# -----------------------------------------------------------------------------
def test_empty_frames():
    detector = VehicleDetector(conf_threshold=0.30)
    assert detector.is_yolo_active is True

    # 1.1 None frame returns empty list
    res_none = detector.detect_frame(None)
    assert res_none == []

    # 1.2 0-dimension frame returns empty list
    res_empty = detector.detect_frame(np.empty((0, 0, 3), dtype=np.uint8))
    assert res_empty == []

    # 1.3 0-size frame returns empty list
    res_zero_shape = detector.detect_frame(np.zeros((0, 0, 0), dtype=np.uint8))
    assert res_zero_shape == []

    # 1.4 API live frame with invalid payload returns 400
    handler = VisionRouteHandler()
    code, err_res = handler.handle_process_live_frame({"image": "invalid_base64_data!!"})
    assert code == 400
    assert err_res["success"] is False
    assert err_res["status"] == "error"


# -----------------------------------------------------------------------------
# 2. Corrupt MP4
# -----------------------------------------------------------------------------
def test_corrupt_mp4():
    processor = VideoProcessor()
    storage = get_video_storage()

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        tf.write(b"\x00\x00\x00 ftypisom" + b"RANDOM_CORRUPT_BYTES_XYZ" * 100)
        corrupt_path = Path(tf.name)

    out_path = corrupt_path.with_name(f"{corrupt_path.stem}_out.mp4")

    try:
        # Direct processor call must raise VideoProcessingError
        with pytest.raises(VideoProcessingError) as exc_info:
            processor.process_video(corrupt_path, out_path)
        assert "OpenCV could not open video file" in str(exc_info.value)

        # Output must NOT exist or be copied from original
        assert not out_path.exists()

        # Job manager submission with corrupt video must fail cleanly
        ok, _, meta = storage.save_upload(corrupt_path.read_bytes(), "corrupt_test.mp4")
        assert ok is True
        mgr = VisionJobManager(max_workers=1)
        job = mgr.submit_job(meta["video_id"], "corrupt_test.mp4")

        import time
        for _ in range(40):
            time.sleep(0.1)
            j = mgr.get_job(job.job_id)
            if j and j.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break

        final_job = mgr.get_job(job.job_id)
        assert final_job is not None
        assert final_job.status == JobStatus.FAILED
        assert "OpenCV could not open video file" in str(final_job.error_message)
    finally:
        corrupt_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# 3. Unavailable YOLO
# -----------------------------------------------------------------------------
def test_unavailable_yolo():
    unavail_detector = VehicleDetector()
    unavail_detector._is_yolo_loaded = False
    unavail_detector.model = None
    unavail_detector.load_error = "CUDA / CoreML weights uninitialized"

    assert unavail_detector.is_yolo_active is False

    # 3.1 detect_frame raises YOLOUnavailableError
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    with pytest.raises(YOLOUnavailableError) as exc_info:
        unavail_detector.detect_frame(dummy_frame)
    assert "CUDA / CoreML weights uninitialized" in str(exc_info.value)

    # 3.2 VideoProcessor fails before processing when detector is unavailable
    processor = VideoProcessor(detector=unavail_detector)
    sample_file = Path("app/static/sample_traffic.mp4")
    out_file = Path("/tmp/unavail_out.mp4")

    with pytest.raises(VideoProcessingError) as exc_info:
        processor.process_video(sample_file, out_file)
    assert "Genuine YOLO vehicle detector is unavailable" in str(exc_info.value)
    assert not out_file.exists()

    # 3.3 VisionRouteHandler reports unavailable on status and 503 on live frame
    handler = VisionRouteHandler()
    # Temporarily substitute detector with unavailable detector
    import traffic_system.computer_vision.detector as det_mod
    orig_detector = det_mod._CACHED_DETECTOR
    try:
        det_mod._CACHED_DETECTOR = unavail_detector
        code, st = handler.handle_get_status()
        assert code == 200
        assert st["data"]["yolo_loaded"] is False
        assert st["data"]["engine"] == "Unavailable"

        code, live_err = handler.handle_process_live_frame({"image": "dummy"})
        assert code == 503
        assert live_err["status"] == "unavailable"
    finally:
        det_mod._CACHED_DETECTOR = orig_detector


# -----------------------------------------------------------------------------
# 4. Zero detections
# -----------------------------------------------------------------------------
def test_zero_detections():
    """Valid video with blank frames produces zero vehicle detections and zero artificial boxes."""
    detector = VehicleDetector(conf_threshold=0.30)

    # 4.1 Detector on black frame returns exactly empty list []
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    dets = detector.detect_frame(blank_frame)
    assert dets == []

    # 4.2 Create a genuine 10-frame playable MP4 of blank frames
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        blank_vid_path = Path(tf.name)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(blank_vid_path), fourcc, 30.0, (640, 480))
    for _ in range(10):
        writer.write(blank_frame)
    writer.release()

    out_path = blank_vid_path.with_name(f"{blank_vid_path.stem}_annotated.mp4")

    try:
        processor = VideoProcessor(detector=detector)
        res = processor.process_video(blank_vid_path, out_path)

        assert res["provenance"] == "Genuine YOLO inference"
        assert res["is_simulation"] is False
        assert res["processing_provenance"] == "GENUINE_YOLO_INFERENCE"
        assert res["total_unique_vehicles"] == 0
        assert all(count == 0 for count in res["class_counts"].values())
        assert res["pcu_telemetry"]["total_pcu"] == 0.0
        assert res["traffic_density"]["peak_density_level"] == "Low"
        assert res["traffic_density"]["peak_occupancy_pct"] == 0.0

        # Output video must exist, be non-empty, and contain exactly 10 frames
        assert out_path.exists()
        assert out_path.stat().st_size > 0
        VideoProcessor.verify_output_video(out_path, expected_min_frames=10)
    finally:
        blank_vid_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# 5. Failed output generation & verification
# -----------------------------------------------------------------------------
def test_failed_output_generation():
    # 5.1 Non-existent file fails verification
    non_existent = Path("/tmp/definitely_not_a_real_output_video_file_9999.mp4")
    with pytest.raises(OutputVerificationError) as exc_info:
        VideoProcessor.verify_output_video(non_existent)
    assert "does not exist" in str(exc_info.value)

    # 5.2 Empty 0-byte file fails verification
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        empty_path = Path(tf.name)
    try:
        with pytest.raises(OutputVerificationError) as exc_info:
            VideoProcessor.verify_output_video(empty_path)
        assert "empty (0 bytes)" in str(exc_info.value)
    finally:
        empty_path.unlink(missing_ok=True)

    # 5.3 Corrupt non-video container fails verification
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        tf.write(b"NOT_A_VALID_MP4_CONTAINER_DATA" * 50)
        corrupt_out = Path(tf.name)
    try:
        with pytest.raises(OutputVerificationError) as exc_info:
            VideoProcessor.verify_output_video(corrupt_out)
        assert "cannot be opened by OpenCV" in str(exc_info.value)
    finally:
        corrupt_out.unlink(missing_ok=True)

    # 5.4 Video with fewer frames than expected fails verification
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        short_path = Path(tf.name)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(short_path), fourcc, 30.0, (320, 240))
    writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
    writer.release()
    try:
        with pytest.raises(OutputVerificationError) as exc_info:
            VideoProcessor.verify_output_video(short_path, expected_min_frames=5)
        assert "contains 1 readable frames (expected at least 5)" in str(exc_info.value)
    finally:
        short_path.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# 6. Frame Stride, Confidence Summary, and Camera Calibration Profiles
# -----------------------------------------------------------------------------
def test_frame_stride_and_confidence_summary():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        vid_path = Path(tf.name)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(vid_path), fourcc, 30.0, (640, 480))
    for _ in range(12):
        writer.write(np.zeros((480, 640, 3), dtype=np.uint8))
    writer.release()

    out_path = vid_path.with_name(f"{vid_path.stem}_out.mp4")
    try:
        # Process with stride=3
        processor = VideoProcessor()
        camera_conf = {
            "camera_id": "test_cctv_highway",
            "expected_lane_bearing_deg": 45.0,
            "roi_relative": (0.2, 0.8, 0.1, 0.9)
        }
        res = processor.process_video(
            input_path=vid_path,
            output_path=out_path,
            frame_stride=3,
            camera_config=camera_conf
        )

        assert res["source_video"]["frame_stride_applied"] == 3
        assert res["source_video"]["effective_fps"] == 10.0
        assert res["source_video"]["total_frames_analyzed"] == 4
        assert "confidence_summary" in res
        assert res["confidence_summary"]["detection_threshold"] == 0.30
        assert "kinematics" in res
        assert res["traffic_density"]["is_calibrated_physical_density"] is False
        assert "pcu_telemetry" in res
        assert "mix_breakdown" in res["pcu_telemetry"]
    finally:
        vid_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)

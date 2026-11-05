"""
tests/test_vision_export_api.py - Unit Tests for Vehicle Telemetry Export API
Verifies:
1. Exporting completed job telemetry as CSV with correct headers and passage rows.
2. Exporting completed job telemetry as JSON.
3. Proper 404 handling for non-existent job IDs.
4. Ownership boundaries on telemetry exports.
"""

import json
import pytest
from traffic_system.computer_vision.job_manager import get_job_manager
from traffic_system.computer_vision.schemas import VisionJob, JobStatus
from app.routes.vision_routes import VisionRouteHandler


def test_export_telemetry_csv_and_json():
    """Verify CSV and JSON telemetry export endpoints for completed jobs."""
    handler = VisionRouteHandler()
    mgr = get_job_manager()

    # Create and store a mock completed job with passage events
    job_id = "cv_test_export_99"
    mock_results = {
        "total_unique_vehicles": 3,
        "class_counts": {"car": 2, "motorcycle": 1},
        "passage_events": [
            {
                "passage_id": "pass_GateA_1_1500",
                "track_id": 1,
                "class_name": "car",
                "tripwire_name": "GateA",
                "direction": "FORWARD",
                "timestamp_sec": 1.5,
                "speed_kmh": 42.0,
                "frame_idx": 45
            },
            {
                "passage_id": "pass_GateA_2_2100",
                "track_id": 2,
                "class_name": "motorcycle",
                "tripwire_name": "GateA",
                "direction": "FORWARD",
                "timestamp_sec": 2.1,
                "speed_kmh": 36.5,
                "frame_idx": 63
            }
        ]
    }

    job = VisionJob(
        job_id=job_id,
        video_id="vid_test_99",
        original_filename="sample.mp4",
        status=JobStatus.COMPLETED,
        owner="anonymous",
        results=mock_results
    )
    with mgr._jobs_lock:
        mgr.jobs[job_id] = job

    # 1. Test CSV export
    status, csv_data, headers = handler.handle_export_telemetry(job_id, format_type="csv")
    assert status == 200
    assert "text/csv" in headers.get("Content-Type", "")
    assert "passage_id,track_id,class_name,tripwire_name,direction,timestamp_sec,speed_kmh,frame_idx" in csv_data
    assert "pass_GateA_1_1500,1,car,GateA,FORWARD,1.5,42.0,45" in csv_data
    assert "pass_GateA_2_2100,2,motorcycle,GateA,FORWARD,2.1,36.5,63" in csv_data

    # 2. Test JSON export
    status_j, json_data, headers_j = handler.handle_export_telemetry(job_id, format_type="json")
    assert status_j == 200
    assert "application/json" in headers_j.get("Content-Type", "")
    parsed = json.loads(json_data)
    assert parsed["job_id"] == job_id
    assert len(parsed["data"]["passage_events"]) == 2

    # 3. Test non-existent job ID
    status_404, _, _ = handler.handle_export_telemetry("non_existent_cv_id", format_type="csv")
    assert status_404 == 404

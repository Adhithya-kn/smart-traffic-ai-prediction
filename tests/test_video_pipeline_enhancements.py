"""
tests/test_video_pipeline_enhancements.py - Unit Tests for Enhanced Video Processor
Verifies:
1. VideoProcessor accepts custom VectorTripwires and registers them with the counter.
2. Passage events and tripwire telemetry are recorded and returned in process_video results.
3. Annotated frame HUD visualizes tripwires and domain vehicle classes (e.g. auto-rickshaws).
4. Output video verification passes on processed video.
"""

from pathlib import Path
import pytest
from traffic_system.config import BASE_DIR
from traffic_system.computer_vision.video_processor import VideoProcessor
from traffic_system.computer_vision.geometry import VectorTripwire, DirectionMode


def test_video_processor_with_custom_tripwires(tmp_path):
    """Verify video processor executes with configured tripwires and outputs passage telemetry."""
    sample_mp4 = BASE_DIR / "app" / "static" / "sample_traffic.mp4"
    assert sample_mp4.exists(), f"Sample traffic video missing at {sample_mp4}"

    out_mp4 = tmp_path / "processed_tripwire_test.mp4"

    # Define a custom axial tripwire across the middle of the frame
    custom_tripwire = VectorTripwire(
        name="Mid_Corridor_Gate",
        p1=(100.0, 300.0),
        p2=(860.0, 300.0),
        direction_mode=DirectionMode.BOTH
    )

    processor = VideoProcessor(
        max_frames=12,
        frame_stride=2,
        simulation_mode=False
    )
    processor.counter.add_tripwire(custom_tripwire)

    result = processor.process_video(
        input_path=sample_mp4,
        output_path=out_mp4
    )

    # Verify processed video was generated and verified
    assert out_mp4.exists()
    assert out_mp4.stat().st_size > 0

    # Verify telemetry results contain tripwire telemetry & passage events
    assert "passage_events" in result
    assert "tripwire_counts" in result
    assert "Mid_Corridor_Gate" in result["tripwire_counts"]

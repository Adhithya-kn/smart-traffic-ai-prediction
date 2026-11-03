"""
traffic_system/computer_vision - Computer Vision Vehicle Analysis Subsystem
Provides sample-video vehicle detection, multi-object tracking, and density estimation.
"""

from traffic_system.computer_vision.schemas import (
    DetectionBox,
    FrameDetectionResult,
    VisionJob,
    JobStatus
)
from traffic_system.computer_vision.detector import VehicleDetector
from traffic_system.computer_vision.tracker import VehicleTracker
from traffic_system.computer_vision.vehicle_counter import VehicleCounter
from traffic_system.computer_vision.density_estimator import TrafficDensityEstimator
from traffic_system.computer_vision.video_processor import VideoProcessor
from traffic_system.computer_vision.job_manager import VisionJobManager, get_job_manager

__all__ = [
    "DetectionBox",
    "FrameDetectionResult",
    "VisionJob",
    "JobStatus",
    "VehicleDetector",
    "VehicleTracker",
    "VehicleCounter",
    "TrafficDensityEstimator",
    "VideoProcessor",
    "VisionJobManager",
    "get_job_manager",
]

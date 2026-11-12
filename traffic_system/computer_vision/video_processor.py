"""
traffic_system/computer_vision/video_processor.py - End-to-End MP4 Video Processing Pipeline
Extracts video frames, executes genuine YOLO detection, tracks vehicles across frames with a custom IoU tracker,
estimates speed and trajectories, converts to Indo-HCM PCU flow, detects incidents,
and writes annotated output video with an Apple HIG luxury telemetry HUD.
Enforces strict output verification, genuine inference invariants, and provenance tracking.
"""

import os
import time
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
import numpy as np

from traffic_system.config import (
    CV_MAX_PROCESSING_FRAMES,
    CV_CONFIDENCE_THRESHOLD
)
from traffic_system.computer_vision.schemas import (
    FrameDetectionResult,
    CameraConfig,
    ConfidenceSummary
)
from traffic_system.computer_vision.detector import (
    get_vehicle_detector,
    VehicleDetector,
    YOLOUnavailableError,
    YOLOInferenceError
)
from traffic_system.computer_vision.tracker import VehicleTracker
from traffic_system.computer_vision.vehicle_counter import VehicleCounter
from traffic_system.computer_vision.density_estimator import TrafficDensityEstimator
from traffic_system.computer_vision.speed_estimator import SpeedEstimator
from traffic_system.computer_vision.pcu_converter import IndoHCMPCUConverter
from traffic_system.computer_vision.incident_detector import IncidentDetector

logger = logging.getLogger("traffic_system.computer_vision.processor")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class VideoProcessingError(RuntimeError):
    """Raised when video processing fails due to unreadable input, encoding errors, or pipeline failures."""
    pass


class OutputVerificationError(VideoProcessingError):
    """Raised when processed output video verification fails."""
    pass


class VideoProcessor:
    """
    Executes vehicle detection, multi-object tracking, speed estimation, Indo-HCM PCU conversion,
    incident detection, and annotated video generation.
    Thread-safe and instantiated per job execution.
    Enforces genuine YOLO inference without synthetic fallback in production.
    """
    def __init__(
        self,
        conf_threshold: float = CV_CONFIDENCE_THRESHOLD,
        max_frames: int = CV_MAX_PROCESSING_FRAMES,
        frame_stride: int = 1,
        detector: Optional[VehicleDetector] = None,
        simulation_mode: bool = False,
        camera_config: Optional[Any] = None
    ):
        self.conf_threshold = conf_threshold
        self.max_frames = max_frames
        self.frame_stride = max(1, int(frame_stride))
        self.detector = detector if detector is not None else get_vehicle_detector()
        self.simulation_mode = simulation_mode
        self.camera_config = camera_config

        self._configure_camera(camera_config)

    def _configure_camera(self, camera_config: Optional[Any] = None) -> None:
        """Configures optical profile, homography calibration, ROI and lane bearings."""
        camera_id = "default_cctv"
        roi_rel = (0.30, 0.95, 0.10, 0.90)
        roi_poly = None
        lane_bearings = [90.0]
        homography_mat = None
        is_calibrated = False
        ppm = 12.5

        if camera_config is not None:
            if isinstance(camera_config, dict):
                camera_id = camera_config.get("camera_id", camera_id)
                roi_rel = camera_config.get("roi_relative", roi_rel)
                roi_poly = camera_config.get("roi_polygon", roi_poly)
                if "expected_lane_bearing_deg" in camera_config:
                    lane_bearings = [float(camera_config["expected_lane_bearing_deg"])]
                elif "expected_lane_bearings_deg" in camera_config:
                    lane_bearings = [float(b) for b in camera_config["expected_lane_bearings_deg"]]
                is_calibrated = camera_config.get("is_homography_calibrated", False)
                if "homography_matrix" in camera_config and camera_config["homography_matrix"] is not None:
                    homography_mat = np.array(camera_config["homography_matrix"], dtype=np.float64)
                    is_calibrated = True
                ppm = camera_config.get("pixels_per_meter", ppm)
            elif hasattr(camera_config, "camera_id"):
                camera_id = camera_config.camera_id
                roi_rel = camera_config.roi_relative
                roi_poly = camera_config.roi_polygon
                lane_bearings = [camera_config.expected_lane_bearing_deg]
                is_calibrated = camera_config.is_homography_calibrated
                if camera_config.homography_matrix is not None:
                    homography_mat = np.array(camera_config.homography_matrix, dtype=np.float64)
                    is_calibrated = True
                ppm = camera_config.pixels_per_meter

        self.speed_estimator = SpeedEstimator(
            camera_id=camera_id,
            homography_matrix=homography_mat,
            is_calibrated=is_calibrated,
            pixels_per_meter=ppm
        )
        self.tracker = VehicleTracker(speed_estimator=self.speed_estimator)
        self.counter = VehicleCounter()
        self.density_estimator = TrafficDensityEstimator(
            camera_id=camera_id,
            roi_relative=roi_rel,
            roi_polygon=roi_poly
        )
        self.incident_detector = IncidentDetector(
            expected_lane_bearings_deg=lane_bearings
        )

        tw_configs = []
        if isinstance(camera_config, dict):
            tw_configs = camera_config.get("tripwires") or []
        elif hasattr(camera_config, "tripwires"):
            tw_configs = getattr(camera_config, "tripwires") or []

        from traffic_system.computer_vision.geometry import VectorTripwire, DirectionMode
        for tw in tw_configs:
            if isinstance(tw, dict):
                name = tw.get("name", "Gate")
                p1 = tw.get("p1", (0.0, 0.0))
                p2 = tw.get("p2", (100.0, 100.0))
                mode = tw.get("direction_mode", "BOTH")
                self.counter.add_tripwire(VectorTripwire(name=name, p1=p1, p2=p2, direction_mode=DirectionMode(mode)))
            elif isinstance(tw, VectorTripwire):
                self.counter.add_tripwire(tw)

    @staticmethod
    def verify_output_video(output_path: Path, expected_min_frames: int = 1) -> None:
        """
        Verifies that the output video exists, is non-empty,
        can be opened by OpenCV, and contains at least expected_min_frames readable frames.
        Raises OutputVerificationError if any check fails.
        """
        target = Path(output_path).resolve()
        if not target.exists():
            raise OutputVerificationError(f"Processed output video does not exist: '{target}'")

        file_size = target.stat().st_size
        if file_size == 0:
            raise OutputVerificationError(f"Processed output video is empty (0 bytes): '{target.name}'")

        if not HAS_CV2:
            raise OutputVerificationError("OpenCV is required to verify processed output video.")

        verify_cap = cv2.VideoCapture(str(target))
        if not verify_cap.isOpened():
            raise OutputVerificationError(
                f"Processed output video cannot be opened by OpenCV (invalid or corrupt container): '{target.name}'"
            )

        frames_counted = 0
        try:
            while frames_counted < expected_min_frames:
                ret, v_frame = verify_cap.read()
                if not ret or v_frame is None or v_frame.size == 0:
                    break
                frames_counted += 1
        finally:
            verify_cap.release()

        if frames_counted < expected_min_frames:
            raise OutputVerificationError(
                f"Processed output video '{target.name}' contains {frames_counted} readable frames "
                f"(expected at least {expected_min_frames})."
            )

    def process_video(
        self,
        input_path: Path,
        output_path: Path,
        progress_callback: Optional[Callable[[float, int, int], None]] = None,
        frame_stride: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        camera_config: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Processes the input video file and writes annotated results.
        Enforces genuine YOLO detection, output verification, and error boundaries.
        progress_callback receives: (progress_fraction, processed_frames, total_frames).
        """
        start_time = time.perf_counter()
        input_file = Path(input_path).resolve()
        output_file = Path(output_path).resolve()
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if not HAS_CV2:
            raise VideoProcessingError("OpenCV (cv2) is required for video processing.")

        if not input_file.exists():
            raise VideoProcessingError(f"Input video file not found: '{input_file}'")

        if input_file.stat().st_size == 0:
            raise VideoProcessingError(f"Input video file '{input_file.name}' is empty (0 bytes).")

        if not self.simulation_mode and not self.detector.is_yolo_active:
            raise VideoProcessingError(
                f"Genuine YOLO vehicle detector is unavailable: {self.detector.load_error or 'Weights not loaded'}"
            )

        if camera_config is not None:
            self._configure_camera(camera_config)

        stride = max(1, frame_stride if frame_stride is not None else self.frame_stride)

        self.tracker.reset()
        self.counter.reset()
        self.speed_estimator.reset()
        self.incident_detector.reset()

        frame_results: List[Dict[str, Any]] = []
        occupancy_readings: List[float] = []
        speed_readings: List[float] = []
        all_incidents: List[Dict[str, Any]] = []
        all_confidences: List[float] = []

        cap = cv2.VideoCapture(str(input_file))
        if not cap.isOpened():
            raise VideoProcessingError(
                f"OpenCV could not open video file '{input_file.name}'. "
                f"The file may be corrupt, truncated, or in an unsupported video container."
            )

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        if fps <= 0.0 or np.isnan(fps):
            fps = 30.0

        orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        file_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if orig_width <= 0 or orig_height <= 0:
            cap.release()
            raise VideoProcessingError(
                f"Video file '{input_file.name}' has invalid dimensions ({orig_width}x{orig_height})."
            )

        # High-performance adaptive dimension normalization:
        # Scale videos wider than 1280px to 1280px maintaining aspect ratio.
        # Accelerates OpenCV rasterization, HUD rendering, and H.264 encoding by 4x-8x.
        MAX_FRAME_WIDTH = 1280
        if orig_width > MAX_FRAME_WIDTH:
            scale_factor = MAX_FRAME_WIDTH / float(orig_width)
            width = MAX_FRAME_WIDTH
            height = int(orig_height * scale_factor)
            if height % 2 != 0:
                height -= 1
        else:
            width = orig_width
            height = orig_height

        effective_fps = max(0.1, fps / stride)
        total_frames = min(file_total if file_total > 0 else self.max_frames, self.max_frames)

        # Setup VideoWriter
        writer = None
        for codec in ["avc1", "mp4v", "H264"]:
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                writer_candidate = cv2.VideoWriter(str(output_file), fourcc, effective_fps, (width, height))
                if writer_candidate.isOpened():
                    writer = writer_candidate
                    break
            except Exception:
                continue

        if writer is None or not writer.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(output_file), fourcc, effective_fps, (width, height))

        if not writer.isOpened():
            cap.release()
            raise VideoProcessingError(f"Failed to initialize VideoWriter for '{output_file}'.")

        cap_frame_idx = 0
        processed_count = 0
        try:
            while cap.isOpened() and processed_count < self.max_frames:
                if timeout_seconds and (time.perf_counter() - start_time) > timeout_seconds:
                    raise VideoProcessingError(
                        f"Video processing exceeded maximum timeout limit of {timeout_seconds:.1f} seconds."
                    )

                ret, frame = cap.read()
                if not ret or frame is None:
                    if cap_frame_idx == 0:
                        raise VideoProcessingError(
                            f"Video file '{input_file.name}' contains no readable video frames or is corrupt."
                        )
                    break

                # Frame sampling via stride
                if (cap_frame_idx % stride) != 0:
                    cap_frame_idx += 1
                    continue

                if width != orig_width or height != orig_height:
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

                # Physical frame timestamp based on source video frame index
                timestamp_sec = round(cap_frame_idx / fps, 3)

                # 1. Detection: Genuine YOLO inference (or explicitly enabled simulation)
                detections = self.detector.detect_frame(
                    frame,
                    conf_threshold=self.conf_threshold,
                    frame_idx=processed_count,
                    allow_simulation=self.simulation_mode,
                    vehicles_only=True
                )

                for det in detections:
                    if det.confidence > 0.0:
                        all_confidences.append(float(det.confidence))

                # 2. Tracking with speed & trajectory using effective_fps
                tracked = self.tracker.update(detections, frame_idx=processed_count, fps=effective_fps)

                # 3. Route-to-Route Transition Counting & Flow Analysis
                count_stats = self.counter.update(
                    tracked,
                    timestamp_sec=timestamp_sec,
                    frame_width=width,
                    frame_height=height
                )

                # 4. Density Estimation
                density_info = self.density_estimator.estimate(tracked, width, height)
                occupancy_readings.append(density_info["occupancy_pct"])

                # 5. Incident Detection & Speed Aggregation
                frame_speeds = []
                for det in tracked:
                    if det.speed_kmh > 0.0:
                        frame_speeds.append(det.speed_kmh)
                        speed_readings.append(det.speed_kmh)

                    incidents = self.incident_detector.update(
                        track_id=det.track_id or 0,
                        box=det,
                        speed_kmh=det.speed_kmh,
                        frame_idx=processed_count,
                        fps=effective_fps
                    )
                    all_incidents.extend(incidents)

                avg_frame_speed = round(sum(frame_speeds) / max(len(frame_speeds), 1), 1) if frame_speeds else 0.0

                # 6. Annotation & HUD Overlay
                self._annotate_frame(frame, tracked, density_info, count_stats, avg_frame_speed, processed_count)
                writer.write(frame)

                if processed_count % 5 == 0 or processed_count == total_frames - 1:
                    frame_results.append({
                        "frame": processed_count,
                        "source_frame": cap_frame_idx,
                        "timestamp_sec": timestamp_sec,
                        "vehicle_count": count_stats.get("current_frame_total", len(tracked)),
                        "current_frame_classes": count_stats.get("current_frame_classes", {}),
                        "cumulative_unique_total": count_stats.get("cumulative_unique_total", 0),
                        "cumulative_classes": count_stats.get("cumulative_classes", {}),
                        "route_transitions_count": count_stats.get("route_transitions_count", 0),
                        "transit_frequency_vpm": count_stats.get("transit_frequency_vpm", 0.0),
                        "average_headway_sec": count_stats.get("average_headway_sec", 0.0),
                        "average_speed_kmh": avg_frame_speed,
                        "density_level": density_info["density_level"],
                        "occupancy_pct": density_info["occupancy_pct"]
                    })

                processed_count += 1
                cap_frame_idx += 1
                if progress_callback:
                    progress_callback(processed_count / max(total_frames, 1), processed_count, total_frames)

            if processed_count == 0:
                raise VideoProcessingError(f"Video file '{input_file.name}' yielded zero readable frames.")
        finally:
            cap.release()
            if writer is not None:
                writer.release()

        # Web-playable MP4 optimization (H.264 faststart header)
        self._ensure_web_compatible_mp4(output_file)

        # Output Verification Gate
        self.verify_output_video(output_file, expected_min_frames=1)

        duration_sec = round(time.perf_counter() - start_time, 2)
        counter_summary = self.counter.get_summary()
        video_duration_sec = round(cap_frame_idx / max(fps, 1.0), 2)

        # Indo-HCM PCU Calculations & Flow Telemetry
        class_counts = counter_summary["class_counts"]
        total_pcu = IndoHCMPCUConverter.calculate_total_pcu(class_counts)
        hourly_pcu_flow = IndoHCMPCUConverter.calculate_hourly_flow(total_pcu, max(video_duration_sec, 1.0))
        pcu_flow_telemetry = IndoHCMPCUConverter.get_flow_telemetry(total_pcu, max(video_duration_sec, 1.0))
        pcu_flow_telemetry["total_pcu"] = total_pcu
        pcu_flow_telemetry["hourly_flow_pcu_per_hr"] = hourly_pcu_flow
        pcu_flow_telemetry["mix_breakdown"] = IndoHCMPCUConverter.get_mix_breakdown(class_counts)

        avg_occ = round(sum(occupancy_readings) / max(len(occupancy_readings), 1), 1)
        peak_occ = round(max(occupancy_readings) if occupancy_readings else 0.0, 1)
        peak_density = "Severe" if peak_occ >= 55.0 else "High" if peak_occ >= 35.0 else "Moderate" if peak_occ >= 15.0 else "Low"
        avg_speed = round(sum(speed_readings) / max(len(speed_readings), 1), 1) if speed_readings else 0.0

        actual_dev = str(getattr(self.detector, "actual_device", "cpu")).upper()
        actual_model = str(getattr(self.detector, "actual_model_name", getattr(self.detector, "model_name", "yolo11n.pt")))

        if self.simulation_mode:
            provenance_label = "Simulation (Demonstration)"
            provenance_code = "SIMULATION"
            engine_label = "Simulation Engine (Demonstration Mode)"
            disclaimer = "Simulated traffic demonstration data. Not genuine vehicle detections."
            is_simulation = True
        else:
            provenance_label = "Genuine YOLO inference"
            provenance_code = "GENUINE_YOLO_INFERENCE"
            engine_label = f"Ultralytics {actual_model} ({actual_dev})"
            disclaimer = "Genuine YOLO computer vision inference on uploaded video frames."
            is_simulation = False

        # Confidence metrics summary
        confidence_summary = {
            "detection_threshold": self.conf_threshold,
            "mean_confidence": round(float(np.mean(all_confidences)), 3) if all_confidences else 0.0,
            "min_confidence": round(float(np.min(all_confidences)), 3) if all_confidences else 0.0,
            "max_confidence": round(float(np.max(all_confidences)), 3) if all_confidences else 0.0,
            "total_detections": len(all_confidences)
        }

        result_data = {
            "provenance": provenance_label,
            "processing_provenance": provenance_code,
            "is_simulation": is_simulation,
            "disclaimer": disclaimer,
            "confidence_summary": confidence_summary,
            "source_video": {
                "filename": input_file.name,
                "file_size_bytes": input_file.stat().st_size if input_file.exists() else 0,
                "resolution": f"{width}x{height}",
                "fps": round(fps, 1),
                "effective_fps": round(effective_fps, 1),
                "frame_stride_applied": stride,
                "total_source_frames": cap_frame_idx,
                "total_frames_analyzed": processed_count,
                "video_duration_seconds": video_duration_sec
            },
            "total_unique_vehicles": counter_summary["total_unique_vehicles"],
            "class_counts": counter_summary["class_counts"],
            "direction_counts": counter_summary.get("direction_counts", {}),
            "class_direction_counts": counter_summary.get("class_direction_counts", {}),
            "route_flow": counter_summary.get("route_flow", {}),
            "tripwire_counts": counter_summary.get("tripwire_counts", {}),
            "passage_events": counter_summary.get("passage_events", []),
            "tracker_diagnostics": self.tracker.get_diagnostics(),
            "pcu_telemetry": pcu_flow_telemetry,
            "kinematics": {
                "space_mean_speed_kmh": avg_speed,
                "speed_samples_count": len(speed_readings),
                "is_calibrated": self.speed_estimator.is_calibrated,
                "calibration_status": "CALIBRATED" if self.speed_estimator.is_calibrated else "UNCALIBRATED_PROXY",
                "calibration_note": (
                    "Physical speed calibrated via planar homography."
                    if self.speed_estimator.is_calibrated
                    else "Uncalibrated optical proxy; requires camera-specific ground control calibration."
                )
            },
            "traffic_density": {
                "average_occupancy_pct": avg_occ,
                "peak_occupancy_pct": peak_occ,
                "peak_density_level": peak_density,
                "measurement_type": "heuristic_optical_occupancy",
                "is_calibrated_physical_density": False,
                "methodology_note": (
                    "2D optical area occupancy heuristic within camera ROI. "
                    "Physical spatial density (veh/km) requires 3D camera extrinsic calibration and road length."
                )
            },
            "incident_summary": self.incident_detector.get_summary(),
            "processing_metrics": {
                "processing_duration_seconds": duration_sec,
                "processing_fps": round(processed_count / max(duration_sec, 0.01), 1),
                "detector_engine": engine_label,
                "model_name": actual_model,
                "inference_device": actual_dev,
                "provenance": provenance_code,
                "is_simulation": is_simulation
            },
            "output_video_path": str(output_file),
            "sample_telemetry": frame_results[:40]
        }

        corridor_id = ""
        camera_id = ""
        capture_time = None
        if self.camera_config:
            if isinstance(self.camera_config, dict):
                corridor_id = str(self.camera_config.get("corridor_id") or "").strip().upper()
                camera_id = str(self.camera_config.get("camera_id") or "").strip()
                capture_time = self.camera_config.get("capture_time")
            elif hasattr(self.camera_config, "corridor_id"):
                corridor_id = str(getattr(self.camera_config, "corridor_id", "") or "").strip().upper()
                camera_id = str(getattr(self.camera_config, "camera_id", "") or "").strip()
                capture_time = getattr(self.camera_config, "capture_time", None)

        from traffic_system.core.road_registry import ROAD_REGISTRY
        if not corridor_id or corridor_id not in ROAD_REGISTRY:
            corridor_id = "RD_BLR_04"

        try:
            from traffic_system.core.measurement import TrafficMeasurement
            measurement = TrafficMeasurement.from_vision_results(
                result_data,
                camera_id=camera_id,
                corridor_id=corridor_id,
                capture_time=capture_time
            )
            result_data["measurement"] = measurement.to_dict()
            result_data["measurements"] = measurement.to_dict()
        except Exception as msr_err:
            logger.debug("TrafficMeasurement generation skipped: %s", msr_err)

        return result_data

    def _annotate_frame(
        self,
        frame: Any,
        tracked_detections: List[Any],
        density_info: Dict[str, Any],
        count_stats: Dict[str, Any],
        avg_speed: float,
        frame_idx: int
    ) -> None:
        """Draws bounding boxes, trajectory ribbons, virtual route gates, and telemetry HUD."""
        if not HAS_CV2:
            return

        frame_h, frame_w = frame.shape[:2]

        # Draw ROI boundary
        roi = density_info["roi_coordinates"]
        cv2.rectangle(
            frame,
            (int(roi["x1"]), int(roi["y1"])),
            (int(roi["x2"]), int(roi["y2"])),
            (255, 200, 0),
            1
        )

        # Draw Virtual Route Ingress Gate A (Emerald Green line)
        gate_a_pct = getattr(self.counter, "gate_a_pct", 0.38)
        gate_a_x = int(frame_w * gate_a_pct)
        cv2.line(frame, (gate_a_x, 0), (gate_a_x, frame_h), (40, 225, 60), 2)
        # Gate A Header Badge
        cv2.rectangle(frame, (gate_a_x - 4, 18), (gate_a_x + 160, 42), (10, 12, 16), -1)
        cv2.rectangle(frame, (gate_a_x - 4, 18), (gate_a_x + 160, 42), (40, 225, 60), 1)
        cv2.putText(frame, "[GATE A: INGRESS]", (gate_a_x + 6, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (40, 225, 60), 1, cv2.LINE_AA)

        # Draw Virtual Route Egress Gate B (Cyan line)
        gate_b_pct = getattr(self.counter, "gate_b_pct", 0.80)
        gate_b_x = int(frame_w * gate_b_pct)
        cv2.line(frame, (gate_b_x, 0), (gate_b_x, frame_h), (240, 200, 20), 2)
        # Gate B Header Badge
        cv2.rectangle(frame, (gate_b_x - 160, 18), (gate_b_x + 4, 42), (10, 12, 16), -1)
        cv2.rectangle(frame, (gate_b_x - 160, 18), (gate_b_x + 4, 42), (240, 200, 20), 1)
        cv2.putText(frame, "[GATE B: EGRESS]", (gate_b_x - 150, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (240, 200, 20), 1, cv2.LINE_AA)

        # Draw Configured Dynamic Vector Tripwires
        tw_counts = getattr(self.counter, "tripwire_counts", {})
        for tw in getattr(self.counter, "tripwires", []):
            pt1 = (int(tw.p1.x), int(tw.p1.y))
            pt2 = (int(tw.p2.x), int(tw.p2.y))
            cv2.line(frame, pt1, pt2, (0, 255, 200), 2)
            mid_x = (pt1[0] + pt2[0]) // 2
            mid_y = (pt1[1] + pt2[1]) // 2
            tot = tw_counts.get(tw.name, {}).get("total", 0)
            badge_txt = f"[{tw.name}: {tot} veh]"
            (bw, bh), _ = cv2.getTextSize(badge_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
            cv2.rectangle(frame, (mid_x - 6, mid_y - bh - 6), (mid_x + bw + 6, mid_y + 4), (10, 12, 16), -1)
            cv2.rectangle(frame, (mid_x - 6, mid_y - bh - 6), (mid_x + bw + 6, mid_y + 4), (0, 255, 200), 1)
            cv2.putText(frame, badge_txt, (mid_x, mid_y - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 200), 1, cv2.LINE_AA)

        # Draw Vehicle Bounding Boxes, Trajectory Ribbons & Route Transition Badges
        for det in tracked_detections:
            cname = (det.class_name or "").lower()
            if cname == "car":
                color = (40, 225, 60)      # Vivid Green for Cars
            elif cname == "bus":
                color = (30, 30, 240)      # Deep Red for Buses
            elif cname == "truck":
                color = (20, 120, 255)     # Coral / Orange for Trucks
            elif cname in ("motorcycle", "bike"):
                color = (240, 200, 20)     # Vivid Cyan for Bikes
            elif cname in ("auto", "auto_rickshaw", "autorickshaw", "three_wheeler"):
                color = (0, 215, 255)      # Bright Amber / Gold for Auto-Rickshaw
            elif cname in ("lcv", "tempo", "mini_truck"):
                color = (255, 180, 50)     # Vivid Turquoise / Teal for LCV
            elif cname in ("bicycle", "cycle"):
                color = (20, 195, 245)     # Golden Yellow for Bicycle
            else:
                color = (40, 225, 60)
            x1, y1, x2, y2 = int(det.x1), int(det.y1), int(det.x2), int(det.y2)

            # Draw Trajectory Ribbon (connecting trailing centroid coordinates)
            if hasattr(det, "trajectory") and len(det.trajectory) > 1:
                pts = [(int(pt[0]), int(pt[1])) for pt in det.trajectory]
                for p_idx in range(len(pts) - 1):
                    alpha_factor = (p_idx + 1) / len(pts)
                    thickness = max(1, int(2 * alpha_factor))
                    cv2.line(frame, pts[p_idx], pts[p_idx + 1], color, thickness)

            # Draw Vehicle Bounding Box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw Corner Accents (tactile HUD style)
            corner_len = min(15, int((x2 - x1) * 0.25), int((y2 - y1) * 0.25))
            if corner_len > 4:
                cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, 3)
                cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, 3)
                cv2.line(frame, (x2, y1), (x2 - corner_len, y1), color, 3)
                cv2.line(frame, (x2, y1), (x2, y1 + corner_len), color, 3)
                cv2.line(frame, (x1, y2), (x1 + corner_len, y2), color, 3)
                cv2.line(frame, (x1, y2), (x1, y2 - corner_len), color, 3)
                cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, 3)
                cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, 3)

            # Draw bottom-center tire contact reticle
            cv2.circle(frame, (int((x1 + x2) / 2), y2), 3, color, -1)

            # Verified Route State Tag
            route_st = getattr(det, "route_status", "APPROACHING")
            if route_st == "TRANSIT_COMPLETE":
                route_tag = "TRANSIT OK"
                badge_border = (40, 225, 60)
            elif route_st == "IN_TRANSIT":
                route_tag = "ROUTE A->B"
                badge_border = (240, 200, 20)
            else:
                route_tag = "APPROACH"
                badge_border = color

            conf_txt = f"{int(det.confidence * 100)}%" if det.confidence > 0 else ""
            label = f"#{det.track_id or 1} {det.class_name.capitalize()} {conf_txt} [{route_tag}]".strip()

            badge_y1 = max(18, y1 - 22)
            badge_y2 = max(24, y1)
            (lbl_w, lbl_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
            cv2.rectangle(frame, (x1, badge_y1), (x1 + lbl_w + 10, badge_y2), (10, 12, 16), -1)
            cv2.rectangle(frame, (x1, badge_y1), (x1 + lbl_w + 10, badge_y2), badge_border, 1)
            cv2.putText(frame, label, (x1 + 5, badge_y2 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)

        # Telemetry HUD in top-left corner
        hud_bg = (10, 12, 16)
        cv2.rectangle(frame, (20, 20), (510, 168), hud_bg, -1)
        cv2.rectangle(frame, (20, 20), (510, 168), (70, 80, 95), 1)

        actual_dev = str(getattr(self.detector, "actual_device", "cpu")).upper()
        actual_model = str(getattr(self.detector, "actual_model_name", getattr(self.detector, "model_name", "YOLO11n")))
        engine_name = "SIMULATION" if self.simulation_mode else f"{actual_model} ({actual_dev})"
        cum_counts = count_stats.get("cumulative_classes", {})
        curr_total = count_stats.get("current_frame_total", len(tracked_detections))
        transits = count_stats.get("route_transitions_count", 0)
        vpm = count_stats.get("transit_frequency_vpm", 0.0)
        headway = count_stats.get("average_headway_sec", 0.0)

        cv2.putText(frame, "ROUTE TRANSIT & FLOW INTELLIGENCE", (35, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2)
        cv2.putText(frame, "Corridor: Gate A (Ingress) -> Gate B (Egress)",
                    (35, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 230, 255), 1)
        cv2.putText(frame, f"Transits: {transits} completed | Flow: {vpm:.1f} veh/min",
                    (35, 96), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 140), 1)
        cv2.putText(frame, f"Avg Headway: {headway:.1f}s | Active in View: {curr_total} | {engine_name}",
                    (35, 122), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 220, 255), 1)
        cv2.putText(frame, f"Cars: {cum_counts.get('car', 0)} | Motos: {cum_counts.get('motorcycle', 0)} | Buses: {cum_counts.get('bus', 0)} | Trucks: {cum_counts.get('truck', 0)}",
                    (35, 148), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

    def _ensure_web_compatible_mp4(self, video_path: Path) -> None:
        """Transcodes OpenCV output to web-optimized H.264 (yuv420p) with faststart header."""
        if not video_path.exists() or video_path.stat().st_size == 0:
            return

        ffmpeg_bin = None
        for candidate in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"]:
            if shutil.which(candidate) or Path(candidate).exists():
                ffmpeg_bin = candidate
                break

        if not ffmpeg_bin:
            return

        temp_transcoded = video_path.with_name(f"{video_path.stem}_web{video_path.suffix}")
        try:
            cmd = [
                str(ffmpeg_bin),
                "-y",
                "-i", str(video_path),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(temp_transcoded)
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)
            if res.returncode == 0 and temp_transcoded.exists() and temp_transcoded.stat().st_size > 0:
                temp_transcoded.replace(video_path)
                logger.info("Transcoded %s to web-compatible H.264 MP4 successfully", video_path.name)
            else:
                err_msg = res.stderr.decode("utf-8", errors="replace") if res.stderr else "unknown error"
                logger.warning("FFmpeg transcode non-zero exit (%d): %s", res.returncode, err_msg)
                if temp_transcoded.exists():
                    temp_transcoded.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("FFmpeg web transcode skipped: %s", e)
            if temp_transcoded.exists():
                temp_transcoded.unlink(missing_ok=True)

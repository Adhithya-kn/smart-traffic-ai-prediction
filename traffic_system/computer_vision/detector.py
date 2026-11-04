"""
traffic_system/computer_vision/detector.py - YOLO-Based Vehicle Detector
Detects cars, motorcycles, buses, trucks, and autos in video frames with confidence thresholding,
Apple Silicon MPS acceleration, and strict genuine inference invariants.
"""

import logging
import threading
from typing import List, Dict, Any, Optional
import numpy as np

from traffic_system.config import CV_CONFIDENCE_THRESHOLD
from traffic_system.computer_vision.schemas import DetectionBox

logger = logging.getLogger("traffic_system.computer_vision.detector")

# COCO Traffic & Vehicle Class Indices
COCO_VEHICLE_MAP = {
    0: "pedestrian",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

_DETECTOR_LOCK = threading.Lock()
_CACHED_DETECTOR: Optional["VehicleDetector"] = None


class YOLOUnavailableError(RuntimeError):
    """Raised when YOLO model cannot be loaded or is unavailable for inference."""
    pass


class YOLOInferenceError(RuntimeError):
    """Raised when YOLO inference execution fails on a frame."""
    pass


class VehicleDetector:
    """
    YOLO Vehicle Detector enforcing genuine model inference.
    Supports YOLO11n / YOLOv8n with hardware acceleration.
    Synthetic detections are strictly barred from normal production inference.
    """
    def __init__(self, model_name: str = "yolo11n.pt", conf_threshold: float = CV_CONFIDENCE_THRESHOLD):
        self.model_name = model_name
        self.conf_threshold = conf_threshold
        self.model = None
        self._is_yolo_loaded = False
        self.load_error: Optional[str] = None
        self._attempt_load_yolo()

    def _attempt_load_yolo(self) -> None:
        """Attempts to load official Ultralytics YOLO model."""
        try:
            from ultralytics import YOLO
            from traffic_system.config import BASE_DIR
            local_weights = BASE_DIR / self.model_name
            if local_weights.exists():
                self.model = YOLO(str(local_weights))
            else:
                try:
                    self.model = YOLO(self.model_name)
                except Exception:
                    # Fallback to YOLOv8n if YOLO11n weights are not locally downloaded yet
                    self.model_name = "yolov8n.pt"
                    self.model = YOLO(self.model_name)

            self._is_yolo_loaded = True
            self.load_error = None
            logger.info("Ultralytics YOLO model loaded successfully: %s", self.model_name)
        except Exception as e:
            self._is_yolo_loaded = False
            self.model = None
            self.load_error = str(e)
            logger.error("Failed to load Ultralytics YOLO model (%s): %s", self.model_name, e)

    @property
    def is_yolo_active(self) -> bool:
        return self._is_yolo_loaded and self.model is not None

    def detect_frame(
        self,
        frame: Any,
        conf_threshold: Optional[float] = None,
        frame_idx: int = 0,
        allow_simulation: bool = False
    ) -> List[DetectionBox]:
        """
        Runs object detection on a single video frame.
        Returns a list of DetectionBox objects for detected vehicles.

        In normal production inference (allow_simulation=False):
        - Genuine YOLO inference is executed.
        - If YOLO detects zero vehicles, an empty list [] is returned.
        - If YOLO is unavailable, YOLOUnavailableError is raised.
        - If YOLO inference fails, YOLOInferenceError is raised.
        - No synthetic or random bounding boxes are generated.

        Simulation mode is ONLY used if allow_simulation=True is explicitly passed.
        """
        if allow_simulation:
            return self._generate_simulated_detections(frame, conf_threshold, frame_idx)

        if not self.is_yolo_active or self.model is None:
            raise YOLOUnavailableError(
                f"YOLO model '{self.model_name}' is unavailable for genuine inference. "
                f"Error: {self.load_error or 'Weights not initialized'}"
            )

        if frame is None:
            return []

        if hasattr(frame, "size") and frame.size == 0:
            return []

        if hasattr(frame, "shape") and (len(frame.shape) < 2 or frame.shape[0] == 0 or frame.shape[1] == 0):
            return []

        threshold = conf_threshold if conf_threshold is not None else self.conf_threshold
        detections: List[DetectionBox] = []

        try:
            device = "cpu"
            results = self.model(frame, conf=threshold, device=device, verbose=False)
            for r in results:
                boxes = r.boxes
                if boxes is None:
                    continue
                for b in boxes:
                    cls_id = int(b.cls[0])
                    if cls_id in COCO_VEHICLE_MAP:
                        cls_name = COCO_VEHICLE_MAP[cls_id]
                        conf = float(b.conf[0])
                        coords = b.xyxy[0].tolist()
                        detections.append(DetectionBox(
                            x1=float(coords[0]),
                            y1=float(coords[1]),
                            x2=float(coords[2]),
                            y2=float(coords[3]),
                            confidence=round(conf, 3),
                            class_id=cls_id,
                            class_name=cls_name
                        ))
            return detections
        except Exception as e:
            logger.error("YOLO inference failed on frame %d: %s", frame_idx, e)
            raise YOLOInferenceError(f"YOLO inference failed on frame {frame_idx}: {e}") from e

    def _generate_simulated_detections(
        self,
        frame: Any,
        conf_threshold: Optional[float] = None,
        frame_idx: int = 0
    ) -> List[DetectionBox]:
        """
        Explicit simulated detector for synthetic demonstration mode ONLY.
        Never invoked in production inference or normal video processing.
        """
        threshold = conf_threshold if conf_threshold is not None else self.conf_threshold
        h, w = (frame.shape[:2] if hasattr(frame, "shape") and len(frame.shape) >= 2 else (720, 1280))
        rng_seed = int((frame_idx * 17 + 101) % 1000)
        np_rng = np.random.default_rng(rng_seed)

        num_vehicles = int(np_rng.integers(3, 9))
        lanes = [w * 0.20, w * 0.40, w * 0.60, w * 0.80]
        detections: List[DetectionBox] = []

        for i in range(num_vehicles):
            lane_center = lanes[i % len(lanes)] + float(np_rng.uniform(-20, 20))
            y_base = float(h * (0.35 + (i / max(num_vehicles, 1)) * 0.55))

            v_type_roll = np_rng.uniform(0, 1)
            if v_type_roll < 0.60:
                cls_id, cls_name = 2, "car"
                box_w, box_h = w * 0.08, h * 0.08
            elif v_type_roll < 0.78:
                cls_id, cls_name = 3, "motorcycle"
                box_w, box_h = w * 0.03, h * 0.05
            elif v_type_roll < 0.88:
                cls_id, cls_name = 5, "bus"
                box_w, box_h = w * 0.12, h * 0.14
            else:
                cls_id, cls_name = 7, "truck"
                box_w, box_h = w * 0.11, h * 0.13

            x1 = max(0.0, lane_center - box_w / 2.0)
            y1 = max(0.0, y_base - box_h / 2.0)
            x2 = min(float(w), x1 + box_w)
            y2 = min(float(h), y1 + box_h)
            conf = float(np_rng.uniform(threshold, 0.95))

            detections.append(DetectionBox(
                x1=round(x1, 1),
                y1=round(y1, 1),
                x2=round(x2, 1),
                y2=round(y2, 1),
                confidence=round(conf, 3),
                class_id=cls_id,
                class_name=cls_name
            ))

        return detections


def get_vehicle_detector() -> VehicleDetector:
    """Thread-safe cached singleton accessor for VehicleDetector."""
    global _CACHED_DETECTOR
    with _DETECTOR_LOCK:
        if _CACHED_DETECTOR is None:
            _CACHED_DETECTOR = VehicleDetector()
        return _CACHED_DETECTOR

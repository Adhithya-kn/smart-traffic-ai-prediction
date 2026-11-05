"""
traffic_system/computer_vision/detector.py - YOLO-Based Vehicle Detector
Detects cars, motorcycles, buses, trucks, and autos in video frames with confidence thresholding,
Apple Silicon MPS acceleration, and strict genuine inference invariants.
"""

import logging
import os
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

# Ensure Ultralytics settings store in writable directory
os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/ultralytics")

from traffic_system.config import CV_CONFIDENCE_THRESHOLD, CV_MODEL_NAME
from traffic_system.computer_vision.schemas import DetectionBox
from traffic_system.core.measurement import canonicalize_class, VEHICLE_CLASSES

logger = logging.getLogger("traffic_system.computer_vision.detector")

# COCO Traffic & Vehicle Class Indices
COCO_VEHICLE_MAP = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

# Non-vehicle classes (tracked for pedestrian safety, but strictly excluded from vehicle counting/totals)
COCO_NON_VEHICLE_MAP = {
    0: "pedestrian"
}

COCO_ALL_CLASSES = {**COCO_VEHICLE_MAP, **COCO_NON_VEHICLE_MAP}

def _ensure_torchvision_nms():
    """
    Ensures torchvision.ops.nms exists and is callable.
    If the compiled C++ operator is missing in stripped environments (e.g. Linux CPU runners),
    falls back transparently to a pure PyTorch NMS implementation.
    """
    try:
        import torch
        import torchvision.ops
        _test_b = torch.zeros((1, 4), dtype=torch.float32)
        _test_s = torch.zeros((1,), dtype=torch.float32)
        _ = torchvision.ops.nms(_test_b, _test_s, 0.5)
    except Exception as exc:
        logger.info("Compiled torchvision::nms operator missing (%s); installing pure PyTorch NMS fallback.", exc)
        try:
            import torch
            import torchvision.ops

            def _pure_pytorch_nms(boxes, scores, iou_threshold):
                if boxes.numel() == 0:
                    return torch.empty((0,), dtype=torch.int64, device=boxes.device)
                x1 = boxes[:, 0]
                y1 = boxes[:, 1]
                x2 = boxes[:, 2]
                y2 = boxes[:, 3]
                areas = (x2 - x1) * (y2 - y1)
                order = scores.argsort(descending=True)
                keep = []
                while order.numel() > 0:
                    i = order[0].item()
                    keep.append(i)
                    if order.numel() == 1:
                        break
                    xx1 = torch.maximum(x1[i], x1[order[1:]])
                    yy1 = torch.maximum(y1[i], y1[order[1:]])
                    xx2 = torch.minimum(x2[i], x2[order[1:]])
                    yy2 = torch.minimum(y2[i], y2[order[1:]])
                    w = torch.clamp(xx2 - xx1, min=0)
                    h = torch.clamp(yy2 - yy1, min=0)
                    inter = w * h
                    ovr = inter / (areas[i] + areas[order[1:]] - inter)
                    inds = torch.where(ovr <= iou_threshold)[0]
                    order = order[inds + 1]
                return torch.tensor(keep, dtype=torch.int64, device=boxes.device)

            torchvision.ops.nms = _pure_pytorch_nms
        except Exception:
            pass

_ensure_torchvision_nms()

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
    Supports Indian-traffic UVH-26 YOLOv11 and standard YOLO11n / YOLOv8n with
    configurable resolution and hardware acceleration.
    Synthetic detections are strictly barred from normal production inference.
    """
    def __init__(
        self,
        model_name: Optional[str] = None,
        conf_threshold: float = CV_CONFIDENCE_THRESHOLD,
        imgsz: int = 640,
        device: str = "auto"
    ):
        self.model_name = model_name or CV_MODEL_NAME
        self.conf_threshold = conf_threshold
        self.imgsz = imgsz
        self.requested_device = device
        self.actual_device = self._resolve_device(device)
        self.actual_model_name = Path(self.model_name).name
        self.model = None
        self.class_map: Dict[int, str] = {}
        self.is_uvh26 = False
        self._is_yolo_loaded = False
        self.load_error: Optional[str] = None
        self._infer_lock = threading.Lock()
        self._attempt_load_yolo()

    @staticmethod
    def _resolve_device(device_req: str) -> str:
        env_dev = os.environ.get("CV_DEVICE") or os.environ.get("YOLO_DEVICE")
        if env_dev:
            req = str(env_dev).lower().strip()
            if req in ("cpu", "mps", "cuda"):
                return req

        req = str(device_req).lower().strip()
        if req in ("cpu", "mps", "cuda"):
            return req
        try:
            import torch
            if torch.backends.mps.is_available() and torch.backends.mps.is_built():
                return "mps"
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def _attempt_load_yolo(self) -> None:
        """Attempts to load official Ultralytics YOLO model."""
        try:
            os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/ultralytics")
            from ultralytics import YOLO
            from traffic_system.config import BASE_DIR

            target_path = Path(self.model_name)
            if not target_path.is_absolute():
                candidate = BASE_DIR / target_path
                if candidate.exists():
                    target_path = candidate
                elif (BASE_DIR / "models" / "uvh26" / "UVH-26-MV-YOLOv11-S.pt").exists() and (
                    "uvh" in str(self.model_name).lower() or not Path(self.model_name).exists()
                ):
                    target_path = BASE_DIR / "models" / "uvh26" / "UVH-26-MV-YOLOv11-S.pt"

            if target_path.exists():
                self.model = YOLO(str(target_path))
                self.actual_model_name = target_path.name
            else:
                try:
                    self.model = YOLO(self.model_name)
                    self.actual_model_name = str(self.model_name)
                except Exception:
                    # Fallback to YOLOv8n if YOLO11n weights are not locally downloaded yet
                    self.model_name = "yolov8n.pt"
                    self.model = YOLO(self.model_name)
                    self.actual_model_name = self.model_name

            names = getattr(self.model, "names", {})
            if names:
                self.is_uvh26 = any(
                    "three-wheeler" in str(v).lower() or "hatchback" in str(v).lower()
                    for v in names.values()
                )
                self.class_map = {
                    int(cls_id): canonicalize_class(cls_name)
                    for cls_id, cls_name in names.items()
                }
            else:
                self.is_uvh26 = False
                self.class_map = dict(COCO_ALL_CLASSES)

            self._is_yolo_loaded = True
            self.load_error = None
            logger.info(
                "Ultralytics YOLO model loaded successfully: %s (engine type: %s)",
                self.actual_model_name,
                "UVH-26 Indian Traffic" if self.is_uvh26 else "COCO"
            )
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
        allow_simulation: bool = False,
        vehicles_only: bool = True
    ) -> List[DetectionBox]:
        """
        Runs object detection on a single video frame.
        Returns a list of DetectionBox objects for detected vehicles.

        In normal production inference (allow_simulation=False):
        - Genuine YOLO inference is executed.
        - If vehicles_only=True (default), pedestrian class 0 is strictly excluded.
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

        with self._infer_lock:
            try:
                try:
                    import torch
                    infer_ctx = torch.inference_mode()
                except Exception:
                    from contextlib import nullcontext
                    infer_ctx = nullcontext()

                with infer_ctx:
                    try:
                        results = self.model(
                            frame,
                            conf=threshold,
                            imgsz=self.imgsz,
                            device=self.actual_device,
                            verbose=False
                        )
                    except Exception as dev_err:
                        # Fallback to CPU if MPS or accelerator fails
                        if self.actual_device != "cpu":
                            logger.warning(
                                "Accelerator '%s' failed on frame %d (%s); falling back to CPU",
                                self.actual_device, frame_idx, dev_err
                            )
                            self.actual_device = "cpu"
                            results = self.model(
                                frame,
                                conf=threshold,
                                imgsz=self.imgsz,
                                device="cpu",
                                verbose=False
                            )
                        else:
                            raise

                # Periodic GPU/MPS memory cache cleanup to avoid memory bloat
                if frame_idx > 0 and frame_idx % 60 == 0:
                    try:
                        import torch
                        if self.actual_device == "mps" and hasattr(torch, "mps"):
                            torch.mps.empty_cache()
                        elif self.actual_device == "cuda" and hasattr(torch, "cuda"):
                            torch.cuda.empty_cache()
                    except Exception:
                        pass

                target_classes = COCO_VEHICLE_MAP if vehicles_only else COCO_ALL_CLASSES
                for r in results:
                    boxes = r.boxes
                    if boxes is None:
                        continue
                    for b in boxes:
                        cls_id = int(b.cls[0])
                        if cls_id in self.class_map:
                            cls_name = self.class_map[cls_id]
                            if vehicles_only and cls_name not in VEHICLE_CLASSES:
                                continue
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
                        elif cls_id in target_classes:
                            cls_name = target_classes[cls_id]
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

    def get_device_info(self) -> Dict[str, Any]:
        """Returns model name, actual device, resolution and threshold metadata."""
        return {
            "model_name": self.actual_model_name,
            "device": self.actual_device,
            "requested_device": self.requested_device,
            "imgsz": self.imgsz,
            "conf_threshold": self.conf_threshold,
            "is_yolo_active": self.is_yolo_active
        }

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
            if v_type_roll < 0.55:
                cls_id, cls_name = 2, "car"
                box_w, box_h = w * 0.08, h * 0.08
            elif v_type_roll < 0.72:
                cls_id, cls_name = 3, "motorcycle"
                box_w, box_h = w * 0.03, h * 0.05
            elif v_type_roll < 0.82:
                cls_id, cls_name = 1, "bicycle"
                box_w, box_h = w * 0.025, h * 0.045
            elif v_type_roll < 0.91:
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

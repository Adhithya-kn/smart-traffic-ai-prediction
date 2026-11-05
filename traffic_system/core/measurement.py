"""
traffic_system/core/measurement.py - Canonical CV Traffic Measurement Contract

Implements the ``TrafficMeasurement`` schema defined in ``docs/CONTRACTS.md`` §2.

Design rules (Phase 2 measurement-first rebuild):
- A measurement is a *typed, validated observation* of a declared capture window.
  It must never be silently padded with fabricated defaults.
- Flow is an hourly rate only when the observation window is at least
  5 minutes (``MIN_FLOW_WINDOW_S``); shorter windows carry a sample estimate and
  ``flow.window_sufficient == False``.
- Density is physical (``veh/km/lane``) only when a camera homography exists and
  a reprojection error is reported; otherwise the measurement carries optical
  ``occupancy_pct`` and ``density.valid == False``.
- Speed is ``homography`` only when calibrated; otherwise ``proxy``.
- ``provenance.quality_flags`` records every degradation explicitly so that
  downstream forecasts and the UI can label PROXY / UNCALIBRATED / SHORT SAMPLE.

The module is dependency-light (stdlib + road registry only) so that it can be
used by the live bridge, the API layer and tests without importing the CV stack.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from traffic_system.core.road_registry import ROAD_REGISTRY
from traffic_system.core.time_utils import now_iso

__all__ = [
    "CANONICAL_CLASSES",
    "VEHICLE_CLASSES",
    "MIN_FLOW_WINDOW_S",
    "MeasurementValidationError",
    "TrafficMeasurement",
    "canonicalize_class",
]

#: Canonical vehicle classes (docs/CONTRACTS.md §1).
CANONICAL_CLASSES = (
    "car",
    "motorcycle",
    "auto_rickshaw",
    "bus",
    "lcv",
    "truck",
    "bicycle",
    "pedestrian",
    "unknown",
)

#: Classes that count as vehicles for flow / PCU. Pedestrians are safety counts
#: and ``unknown`` objects are never counted (docs/CONTRACTS.md §1).
VEHICLE_CLASSES = (
    "car",
    "motorcycle",
    "auto_rickshaw",
    "bus",
    "lcv",
    "truck",
    "bicycle",
)

#: Minimum observation window before a count may be reported as an hourly flow.
MIN_FLOW_WINDOW_S = 300.0

#: Maximum accepted observation window (one day); guards against unit mistakes.
MAX_WINDOW_S = 86_400.0

_CORRIDOR_RE = re.compile(r"^RD_BLR_\d{2}$")

#: Aliases seen in historical CV results / detector outputs -> canonical class.
_CLASS_ALIASES: Dict[str, str] = {
    "car": "car",
    "automobile": "car",
    "taxi": "car",
    "van": "car",  # canonical guidance folds vans into car when indistinguishable
    "hatchback": "car",
    "sedan": "car",
    "suv": "car",
    "muv": "car",
    "motorcycle": "motorcycle",
    "motorbike": "motorcycle",
    "two_wheeler": "motorcycle",
    "two-wheeler": "motorcycle",
    "bike": "motorcycle",
    "auto": "auto_rickshaw",
    "auto_rickshaw": "auto_rickshaw",
    "auto-rickshaw": "auto_rickshaw",
    "three_wheeler": "auto_rickshaw",
    "three-wheeler": "auto_rickshaw",
    "rickshaw": "auto_rickshaw",
    "bus": "bus",
    "minibus": "bus",
    "mini-bus": "bus",
    "lcv": "lcv",
    "light_commercial": "lcv",
    "light-commercial": "lcv",
    "truck": "truck",
    "heavy_vehicle": "truck",
    "tempo": "lcv",
    "tempo-traveller": "lcv",
    "tempo_traveller": "lcv",
    "bicycle": "bicycle",
    "cycle": "bicycle",
    "pedestrian": "pedestrian",
    "person": "pedestrian",
    "people": "pedestrian",
    "unknown": "unknown",
    "others": "unknown",
}


class MeasurementValidationError(ValueError):
    """Raised when a measurement is missing, malformed or not forecast-usable."""


def canonicalize_class(name: Any) -> str:
    """Maps a detector/legacy class label onto the canonical class set."""
    key = str(name or "").strip().lower().replace(" ", "_")
    return _CLASS_ALIASES.get(key, "unknown")


# ---------------------------------------------------------------------------
# Primitive coercion helpers
# ---------------------------------------------------------------------------
def _finite_float(value: Any, field_name: str) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise MeasurementValidationError(f"{field_name} must be numeric, got {value!r}")
    if not math.isfinite(f):
        raise MeasurementValidationError(f"{field_name} must be finite, got {value!r}")
    return f


def _count_int(value: Any, field_name: str) -> int:
    f = _finite_float(value, field_name)
    if f < 0:
        raise MeasurementValidationError(f"{field_name} must be >= 0, got {f}")
    if abs(f - round(f)) > 1e-6:
        raise MeasurementValidationError(f"{field_name} must be an integer count, got {f}")
    return int(round(f))


def parse_capture_time(value: Any, field_name: str = "capture_time") -> datetime:
    """
    Parses an ISO-8601 timestamp. Naive timestamps are interpreted as
    Asia/Kolkata (IST, UTC+05:30), matching the Bengaluru deployment context.
    """
    if isinstance(value, datetime):
        dt = value
    elif value is None or str(value).strip() == "":
        raise MeasurementValidationError(f"{field_name} is required (ISO-8601)")
    else:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            raise MeasurementValidationError(
                f"{field_name} must be ISO-8601, got {value!r}"
            )
    if dt.tzinfo is None:
        from zoneinfo import ZoneInfo

        dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return dt


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _normalize_incidents(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise MeasurementValidationError("incidents must be a list")
    out: List[Dict[str, Any]] = []
    for inc in raw:
        if not isinstance(inc, dict):
            raise MeasurementValidationError("each incident must be an object")
        out.append(dict(inc))
    return out


def _pick(mapping: Any, *keys: str) -> Any:
    """Returns the first present, non-None value among ``keys`` of a mapping."""
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


@dataclass
class TrafficMeasurement:
    """
    Validated observation of one corridor over one declared capture window.

    Field semantics follow docs/CONTRACTS.md §2. Construct via ``from_dict`` or
    ``from_vision_results``; the dataclass ``__post_init__`` normalizes and
    validates every field, raising :class:`MeasurementValidationError` on
    invalid input rather than substituting defaults.
    """

    corridor_id: str
    capture_start: str
    capture_end: str
    interval_s: float
    measurement_id: str = ""
    camera_id: str = ""
    counts: Dict[str, int] = field(default_factory=dict)
    flow: Dict[str, Any] = field(default_factory=dict)
    occupancy_pct: float = 0.0
    density: Dict[str, Any] = field(default_factory=dict)
    speed: Dict[str, Any] = field(default_factory=dict)
    incidents: List[Dict[str, Any]] = field(default_factory=list)
    calibration: Dict[str, Any] = field(default_factory=dict)
    model: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    # -- lifecycle ----------------------------------------------------------
    def __post_init__(self) -> None:
        self.validate()

    # -- normalization / validation ----------------------------------------
    def validate(self) -> "TrafficMeasurement":
        """
        Normalizes and validates the measurement in place; returns ``self``.
        Raises :class:`MeasurementValidationError` on any invalid field.
        """
        # identity
        self.corridor_id = str(self.corridor_id or "").strip().upper()
        if not _CORRIDOR_RE.match(self.corridor_id):
            raise MeasurementValidationError(
                f"corridor_id must match RD_BLR_xx, got {self.corridor_id!r}"
            )
        if self.corridor_id not in ROAD_REGISTRY:
            raise MeasurementValidationError(
                f"corridor_id {self.corridor_id!r} is not a registered Bengaluru corridor"
            )
        self.camera_id = str(self.camera_id or "").strip()
        self.measurement_id = str(self.measurement_id or "").strip() or (
            f"msr_{uuid.uuid4().hex[:10]}"
        )

        # capture window
        start = parse_capture_time(self.capture_start, "capture_start")
        end = parse_capture_time(self.capture_end, "capture_end")
        if end < start:
            raise MeasurementValidationError("capture_end must not precede capture_start")
        measured_window = (end - start).total_seconds()
        interval = _finite_float(self.interval_s, "interval_s")
        if interval < 0:
            raise MeasurementValidationError("interval_s must be >= 0")
        if interval > MAX_WINDOW_S:
            raise MeasurementValidationError("interval_s exceeds the 24 h measurement limit")
        if interval == 0:
            if measured_window > 0:
                interval = measured_window
            else:
                interval = 0.0
        elif measured_window > 0:
            tolerance = max(1.0, 0.05 * interval)
            if abs(interval - measured_window) > tolerance:
                raise MeasurementValidationError(
                    "interval_s is inconsistent with the capture window "
                    f"({interval}s vs {measured_window:.1f}s)"
                )
        self.capture_start = _iso(start)
        self.capture_end = _iso(end)
        self.interval_s = round(interval, 3)

        # counts
        raw_counts = self.counts if self.counts is not None else {}
        if not isinstance(raw_counts, dict):
            raise MeasurementValidationError("counts must be an object")
        counts = {cls: 0 for cls in CANONICAL_CLASSES}
        for raw_name, raw_value in raw_counts.items():
            cls = canonicalize_class(raw_name)
            if cls not in counts:
                raise MeasurementValidationError(f"unsupported class {raw_name!r}")
            counts[cls] += _count_int(raw_value, f"counts.{raw_name}")
        self.counts = counts

        # flow
        raw_flow = self.flow if self.flow is not None else {}
        if not isinstance(raw_flow, dict):
            raise MeasurementValidationError("flow must be an object")
        vph = raw_flow.get("vph")
        pcu_per_h = raw_flow.get("pcu_per_h")
        vph = None if vph is None else round(_finite_float(vph, "flow.vph"), 1)
        pcu_per_h = (
            None
            if pcu_per_h is None
            else round(_finite_float(pcu_per_h, "flow.pcu_per_h"), 1)
        )
        if vph is not None and vph < 0:
            raise MeasurementValidationError("flow.vph must be >= 0")
        if pcu_per_h is not None and pcu_per_h < 0:
            raise MeasurementValidationError("flow.pcu_per_h must be >= 0")
        window_sufficient = bool(self.interval_s >= MIN_FLOW_WINDOW_S)
        flow_source = str(raw_flow.get("source") or "").strip()
        if not flow_source:
            if vph is not None or pcu_per_h is not None:
                flow_source = "measured"
            else:
                flow_source = "none"
        if vph is not None and not window_sufficient:
            # short-window rates are sample estimates, never declared sufficient
            window_sufficient = False
        self.flow = {
            "vph": vph,
            "pcu_per_h": pcu_per_h,
            "window_sufficient": window_sufficient,
            "window_s": self.interval_s,
            "source": flow_source,
        }

        # occupancy
        occ = _finite_float(self.occupancy_pct if self.occupancy_pct is not None else 0.0, "occupancy_pct")
        if occ < 0 or occ > 100:
            raise MeasurementValidationError(f"occupancy_pct must be 0-100, got {occ}")
        self.occupancy_pct = round(occ, 1)

        # calibration
        raw_cal = self.calibration if self.calibration is not None else {}
        if not isinstance(raw_cal, dict):
            raise MeasurementValidationError("calibration must be an object")
        is_calibrated = bool(raw_cal.get("is_calibrated", False))
        method = raw_cal.get("method")
        reproj = raw_cal.get("reprojection_error_px")
        if reproj is not None:
            reproj = round(_finite_float(reproj, "calibration.reprojection_error_px"), 3)
            if reproj < 0:
                raise MeasurementValidationError("reprojection_error_px must be >= 0")
        if is_calibrated and reproj is None:
            raise MeasurementValidationError(
                "calibration.is_calibrated requires a reported reprojection_error_px"
            )
        self.calibration = {
            "is_calibrated": is_calibrated,
            "method": str(method) if method else (None),
            "reprojection_error_px": reproj,
        }

        # speed
        raw_speed = self.speed if self.speed is not None else {}
        if not isinstance(raw_speed, dict):
            raise MeasurementValidationError("speed must be an object")
        speed_value = _finite_float(_pick(raw_speed, "value_kmh", "speed_kmh") or 0.0, "speed.value_kmh")
        if speed_value < 0 or speed_value > 300:
            raise MeasurementValidationError("speed.value_kmh must be within 0-300 km/h")
        speed_method = str(raw_speed.get("method") or "proxy").strip().lower()
        if speed_method not in ("proxy", "homography"):
            raise MeasurementValidationError("speed.method must be 'proxy' or 'homography'")
        speed_calibrated = bool(raw_speed.get("calibrated", False))
        if speed_calibrated and not (speed_method == "homography" and is_calibrated):
            # never claim calibration without the homography + reprojection error
            speed_calibrated = False
        self.speed = {
            "value_kmh": round(speed_value, 2),
            "method": speed_method,
            "calibrated": speed_calibrated,
        }

        # density
        raw_density = self.density if self.density is not None else {}
        if not isinstance(raw_density, dict):
            raise MeasurementValidationError("density must be an object")
        density_value = _finite_float(_pick(raw_density, "value") or 0.0, "density.value")
        if density_value < 0:
            raise MeasurementValidationError("density.value must be >= 0")
        density_method = str(raw_density.get("method") or "occupancy").strip().lower()
        if density_method not in ("occupancy", "calibrated"):
            raise MeasurementValidationError("density.method must be 'occupancy' or 'calibrated'")
        density_valid = bool(raw_density.get("valid", False)) and density_method == "calibrated" and is_calibrated
        self.density = {
            "value": round(density_value, 3),
            "unit": "veh/km/lane",
            "method": density_method,
            "valid": density_valid,
        }

        # incidents
        self.incidents = _normalize_incidents(self.incidents)

        # model metadata (documented, never invented device/class claims)
        raw_model = self.model if self.model is not None else {}
        if not isinstance(raw_model, dict):
            raise MeasurementValidationError("model must be an object")
        model_classes = raw_model.get("classes") or []
        if not isinstance(model_classes, (list, tuple)):
            raise MeasurementValidationError("model.classes must be a list")
        imgsz = raw_model.get("imgsz")
        conf = raw_model.get("conf")
        self.model = {
            "name": str(raw_model.get("name") or "unknown"),
            "version": str(raw_model.get("version") or "unknown"),
            "classes": [canonicalize_class(c) for c in model_classes],
            "imgsz": None if imgsz is None else _count_int(imgsz, "model.imgsz"),
            "conf": None if conf is None else round(_finite_float(conf, "model.conf"), 3),
            "device": str(raw_model.get("device") or "unknown"),
        }

        # provenance
        raw_prov = self.provenance if self.provenance is not None else {}
        if not isinstance(raw_prov, dict):
            raise MeasurementValidationError("provenance must be an object")
        source = str(raw_prov.get("source") or "").strip()
        if not source:
            raise MeasurementValidationError("provenance.source is required")
        flags = raw_prov.get("quality_flags") or []
        if not isinstance(flags, (list, tuple)):
            raise MeasurementValidationError("provenance.quality_flags must be a list")
        self.provenance = {
            "source": source,
            "is_live": bool(raw_prov.get("is_live", False)),
            "is_simulated": bool(raw_prov.get("is_simulated", False)),
            "quality_flags": [str(f) for f in dict.fromkeys(flags)],
        }

        self._append_derived_quality_flags()
        return self

    def _append_derived_quality_flags(self) -> None:
        flags = list(self.provenance["quality_flags"])
        if not self.camera_id:
            flags.append("camera_id_missing")
        if self.interval_s <= 0:
            flags.append("interval_unknown")
        elif self.interval_s < MIN_FLOW_WINDOW_S:
            flags.append("sample_window_lt_300s")
        if not self.speed["calibrated"]:
            flags.append("uncalibrated_speed_proxy")
        if not self.calibration["is_calibrated"]:
            flags.append("camera_uncalibrated")
        if self.provenance["is_simulated"]:
            flags.append("simulated")
        self.provenance["quality_flags"] = list(dict.fromkeys(flags))

    # -- derived queries ----------------------------------------------------
    @property
    def vehicle_count(self) -> int:
        """Total counted vehicles (pedestrians and unknown excluded)."""
        return int(sum(self.counts.get(cls, 0) for cls in VEHICLE_CLASSES))

    def has_measured_flow(self) -> bool:
        flow = self.flow or {}
        return flow.get("vph") is not None or flow.get("pcu_per_h") is not None

    def has_measured_counts(self) -> bool:
        return self.vehicle_count > 0

    def capture_datetime(self) -> datetime:
        return parse_capture_time(self.capture_start, "capture_start")

    def forecast_window(self) -> Dict[str, str]:
        """The next-hour forecast window: [capture_start, capture_start + 1 h]."""
        start = self.capture_datetime()
        return {
            "from": _iso(start),
            "to": _iso(start + timedelta(hours=1)),
        }

    def validate_for_forecast(self, require_measured_flow: bool = True) -> "TrafficMeasurement":
        """
        Returns ``self`` if the measurement can feed the next-hour forecast,
        else raises. A forecast needs a positive measured speed and either a
        measured flow or measured occupancy (the latter only for the explicitly
        labelled heuristic fallback handled by the live bridge).
        """
        if self.speed["value_kmh"] <= 0:
            raise MeasurementValidationError(
                "forecast requires a positive measured speed; no fabricated default is used"
            )
        if require_measured_flow and not self.has_measured_flow():
            raise MeasurementValidationError(
                "forecast requires measured flow (count or pcu); occupancy-only payloads "
                "must use the explicitly labelled fallback path"
            )
        if not require_measured_flow:
            if not self.has_measured_flow() and self.occupancy_pct <= 0:
                raise MeasurementValidationError(
                    "forecast requires measured flow, or measured occupancy for the "
                    "explicitly labelled heuristic fallback"
                )
        return self

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable dict matching docs/CONTRACTS.md §2."""
        return {
            "measurement_id": self.measurement_id,
            "camera_id": self.camera_id,
            "corridor_id": self.corridor_id,
            "capture_start": self.capture_start,
            "capture_end": self.capture_end,
            "interval_s": self.interval_s,
            "counts": dict(self.counts),
            "flow": dict(self.flow),
            "occupancy_pct": self.occupancy_pct,
            "density": dict(self.density),
            "speed": dict(self.speed),
            "incidents": [dict(i) for i in self.incidents],
            "calibration": dict(self.calibration),
            "model": dict(self.model),
            "provenance": {
                "source": self.provenance["source"],
                "is_live": self.provenance["is_live"],
                "is_simulated": self.provenance["is_simulated"],
                "quality_flags": list(self.provenance["quality_flags"]),
            },
        }

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrafficMeasurement":
        """Builds a measurement from an API/ingest payload (contract shape)."""
        if not isinstance(data, dict) or not data:
            raise MeasurementValidationError("measurement payload must be a non-empty object")
        if "counts" not in data and "flow" not in data:
            raise MeasurementValidationError(
                "measurement payload must include counts and/or flow; refusing to "
                "accept a partial payload"
            )
        return cls(
            measurement_id=str(data.get("measurement_id") or ""),
            camera_id=str(data.get("camera_id") or ""),
            corridor_id=str(data.get("corridor_id") or ""),
            capture_start=data.get("capture_start") or "",
            capture_end=data.get("capture_end") or "",
            interval_s=data.get("interval_s", 0.0),
            counts=data.get("counts") or {},
            flow=data.get("flow") or {},
            occupancy_pct=data.get("occupancy_pct", 0.0),
            density=data.get("density") or {},
            speed=data.get("speed") or {},
            incidents=data.get("incidents") or [],
            calibration=data.get("calibration") or {},
            model=data.get("model") or {},
            provenance=data.get("provenance") or {},
        )

    # -- adapter from the existing CV job result ---------------------------
    @classmethod
    def from_vision_results(
        cls,
        job_results: Dict[str, Any],
        camera_id: str = "",
        corridor_id: str = "",
        capture_time: Any = None,
    ) -> "TrafficMeasurement":
        """
        Builds a measurement from a computer-vision job result payload.

        Tolerates both the historical result shape (``class_counts``,
        ``pcu_telemetry``, ``kinematics``, ``traffic_density``) and the canonical
        measurement additions. Fields the CV output does not provide stay at
        their neutral value and are surfaced via ``provenance.quality_flags`` —
        in particular a missing capture time is recorded as inferred from the
        request clock rather than being treated as a live observation.
        """
        if not isinstance(job_results, dict) or not job_results:
            raise MeasurementValidationError(
                "vision results payload must be a non-empty object"
            )

        quality_flags: List[str] = []
        source = "vision_job_results"

        # --- capture window -------------------------------------------------
        capture_start = capture_time or _pick(
            job_results, "capture_start", "capture_time", "recorded_at"
        )
        if capture_start is None:
            capture_start = now_iso()
            quality_flags.append("capture_time_inferred_from_request_clock")
        start_dt = parse_capture_time(capture_start, "capture_time")

        # --- interval -------------------------------------------------------
        pcu_info = job_results.get("pcu_telemetry") or {}
        src_video = job_results.get("source_video") or {}
        interval_raw = _pick(
            job_results, "interval_s", "duration_s", "sample_duration_seconds"
        )
        if interval_raw is None:
            interval_raw = _pick(pcu_info, "sample_duration_seconds", "window_s")
        if interval_raw is None:
            interval_raw = _pick(src_video, "video_duration_seconds")
        if interval_raw is None:
            interval_raw = 0.0
            quality_flags.append("interval_unknown")
        interval_s = _finite_float(interval_raw, "interval_s")
        if interval_s < 0:
            raise MeasurementValidationError("vision result interval must be >= 0")
        end_dt = start_dt + timedelta(seconds=interval_s)

        # --- counts ---------------------------------------------------------
        counts: Dict[str, int] = {}
        raw_counts = job_results.get("counts")
        if raw_counts is None:
            raw_counts = job_results.get("class_counts")
        if isinstance(raw_counts, dict):
            for name, value in raw_counts.items():
                try:
                    counts[canonicalize_class(name)] = counts.get(
                        canonicalize_class(name), 0
                    ) + _count_int(value, f"counts.{name}")
                except MeasurementValidationError:
                    quality_flags.append(f"invalid_count:{name}")
        if not counts:
            mix = pcu_info.get("mix_breakdown") or {}
            classes = mix.get("classes") if isinstance(mix, dict) else None
            if isinstance(classes, dict):
                for name, detail in classes.items():
                    try:
                        counts[canonicalize_class(name)] = _count_int(
                            (detail or {}).get("count", 0), f"counts.{name}"
                        )
                    except MeasurementValidationError:
                        quality_flags.append(f"invalid_count:{name}")
        total_unique = job_results.get("total_unique_vehicles")
        if not counts and total_unique is not None:
            # legacy payloads may only expose the aggregate unique count; it is
            # kept as a class-less count so flow can still be derived honestly.
            counts["unknown"] = _count_int(total_unique, "total_unique_vehicles")
            quality_flags.append("classes_unavailable")

        measured_vehicle_count = sum(counts.get(c, 0) for c in VEHICLE_CLASSES)

        # --- flow -----------------------------------------------------------
        vph: Optional[float] = None
        pcu_per_h: Optional[float] = None
        flow_source = "none"
        pcu_measured = _pick(pcu_info, "extrapolated_hourly_flow_pcu", "hourly_flow_pcu_per_hr")
        if pcu_measured is not None:
            pcu_per_h = round(_finite_float(pcu_measured, "flow.pcu_per_h"), 1)
            flow_source = "pcu_telemetry"
        if measured_vehicle_count > 0 and interval_s > 0:
            vph = round(measured_vehicle_count / interval_s * 3600.0, 1)
            flow_source = "counted_vehicles"
        elif total_unique is not None and not counts.get("unknown") and interval_s > 0:
            vph = round(_count_int(total_unique, "total_unique_vehicles") / interval_s * 3600.0, 1)
            flow_source = "unique_vehicle_count"
        if vph is None and pcu_per_h is not None:
            quality_flags.append("vehicle_flow_unavailable_pcu_only")

        # --- occupancy / speed / calibration -------------------------------
        density_info = job_results.get("traffic_density") or {}
        occupancy = _pick(density_info, "average_occupancy_pct", "occupancy_pct", "peak_occupancy_pct")
        occupancy_pct = 0.0 if occupancy is None else _finite_float(occupancy, "occupancy_pct")

        kinematics = job_results.get("kinematics") or {}
        speed_value = _pick(kinematics, "space_mean_speed_kmh", "value_kmh", "mean_speed_kmh")
        speed_kmh = 0.0 if speed_value is None else _finite_float(speed_value, "speed.value_kmh")
        speed_calibrated = bool(
            _pick(kinematics, "is_calibrated", "calibrated") or False
        )
        if speed_calibrated:
            speed_method = "homography"
        else:
            speed_method = "proxy"

        calibration_payload = job_results.get("calibration") or {}
        calib_certified = bool(calibration_payload.get("is_calibrated", False))
        reproj = calibration_payload.get("reprojection_error_px")
        if speed_calibrated and not calib_certified:
            # preserved for backwards compatibility: historical jobs report
            # `is_calibrated` on the speed estimator, which is not a verified
            # camera homography input to the measurement contract.
            quality_flags.append("speed_estimator_calibration_unverified")

        # --- incidents ------------------------------------------------------
        incidents = job_results.get("incidents")
        if incidents is None:
            summary = job_results.get("incident_summary") or {}
            incidents = summary.get("incidents") if isinstance(summary, dict) else None
        if not isinstance(incidents, list):
            incidents = []

        # --- model metadata -------------------------------------------------
        proc = job_results.get("processing_metrics") or {}
        confidence_summary = job_results.get("confidence_summary") or {}
        model_name = _pick(proc, "model_name") or job_results.get("engine") or "unknown"
        model = {
            "name": model_name,
            "version": str(job_results.get("model_version") or "v1"),
            "classes": list(CANONICAL_CLASSES),
            "imgsz": job_results.get("imgsz"),
            "conf": _pick(confidence_summary, "detection_threshold"),
            "device": _pick(proc, "inference_device") or "unknown",
        }

        provenance = {
            "source": source,
            "is_live": False,  # uploaded/processed video is not a live sensor reading
            "is_simulated": bool(job_results.get("is_simulation", False)),
            "quality_flags": quality_flags,
        }

        return cls(
            camera_id=camera_id or str(job_results.get("camera_id") or ""),
            corridor_id=corridor_id or str(job_results.get("corridor_id") or ""),
            capture_start=_iso(start_dt),
            capture_end=_iso(end_dt),
            interval_s=interval_s,
            counts=counts,
            flow={
                "vph": vph,
                "pcu_per_h": pcu_per_h,
                "source": flow_source,
            },
            occupancy_pct=occupancy_pct,
            density={
                "value": 0.0,
                "unit": "veh/km/lane",
                "method": "calibrated" if calib_certified else "occupancy",
                "valid": False,
            },
            speed={
                "value_kmh": speed_kmh,
                "method": speed_method,
                "calibrated": bool(speed_calibrated and calib_certified),
            },
            incidents=incidents,
            calibration={
                "is_calibrated": calib_certified,
                "method": calibration_payload.get("method"),
                "reprojection_error_px": reproj,
            },
            model=model,
            provenance=provenance,
        )

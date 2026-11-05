# Implementation Contracts (Phase 1–4)

**Purpose:** keep parallel workstreams compatible. This file is authoritative for shared names/shapes. Do not change a contract without messaging the Lead.

---

## 1. Canonical vehicle classes

Use these names in code, APIs, UI, and PCU math:

```
car
motorcycle
auto_rickshaw
bus
lcv
truck
bicycle
pedestrian
unknown
```

- `pc/metrics` may aggregate `lcv` into truck if needed, but display `lcv` separately when available.
- `unknown` is never counted as a vehicle for flow/prediction.
- Pedestrians are counted separately and never priced as PCU.

### UVH-26 model mapping (14 classes → canonical)
```
Hatchback, Sedan, SUV, MUV, Van → car
Two-wheeler → motorcycle
Three-wheeler → auto_rickshaw
Bus, Mini-bus → bus
Tempo-traveller → lcv
LCV → lcv
Truck → truck
Bicycle → bicycle
Others → unknown
```

Model file: `models/uvh26/UVH-26-MV-YOLOv11-S.pt` (Apache-2.0, UVH-26/MV, IISc AIM; classes from `models/uvh26/uvh_classes.txt`).

---

## 2. `TrafficMeasurement` (new module `traffic_system/core/measurement.py`)

```json
{
  "measurement_id": "str",
  "camera_id": "str",
  "corridor_id": "RD_BLR_xx",
  "capture_start": "ISO-8601",
  "capture_end": "ISO-8601",
  "interval_s": 0.0,
  "counts": {
    "car": 0, "motorcycle": 0, "auto_rickshaw": 0, "bus": 0,
    "lcv": 0, "truck": 0, "bicycle": 0, "pedestrian": 0, "unknown": 0
  },
  "flow": {"vph": 0.0, "pcu_per_h": 0.0, "window_sufficient": false},
  "occupancy_pct": 0.0,
  "density": {"value": 0.0, "unit": "veh/km/lane", "method": "occupancy|calibrated", "valid": false},
  "speed": {"value_kmh": 0.0, "method": "proxy|homography", "calibrated": false},
  "incidents": [],
  "calibration": {"is_calibrated": false, "method": null, "reprojection_error_px": null},
  "model": {"name": "UVH-26-MV-YOLOv11-S", "version": "v1", "classes": [], "imgsz": 960, "conf": 0.25, "device": "mps"},
  "provenance": {"source": "uploaded_video", "is_live": false, "is_simulated": false, "quality_flags": []}
}
```

Rules:
- `counts` are integer observations.
- `flow.window_sufficient` is true only when `interval_s >= 300`; otherwise `flow.vph` is a **sample estimate** and `pcu_per_h` may still be shown with that label.
- `density.valid` and `speed.calibrated` are false unless a camera homography exists and reprojection error is reported.
- `measurement.to_dict()` must be JSON-serializable.
- `TrafficMeasurement.from_vision_results(job_results, camera_id, corridor_id, capture_time)` builds it from the existing CV job result.

---

## 3. API contracts (Lead owns `app/server.py`)

```
GET  /api/vision/cameras
POST /api/vision/cameras                 {camera_id, corridor_id, roi_polygon, lane_polygons, homography|points, pixels_per_meter}
POST /api/vision/cameras/{id}/calibrate  {src_points, dst_points_meters}
GET  /api/vision/cameras/{id}
POST /api/vision/process                 add camera_id, capture_time
GET  /api/vision/results/{job_id}        includes measurements: TrafficMeasurement
GET  /api/traffic-state/{corridor_id}
POST /api/traffic-state/ingest           admin; body = TrafficMeasurement
GET  /api/evaluation/summary             CV metrics + ML baselines + system latency
GET  /api/metrics                        add baselines, feature schema, synthetic caveat
```

- All mutating endpoints require Traffic Management auth.
- Empty/partial measurement payloads return 400; no fabricated defaults.
- `/api/vision/live/actuate` remains an alias only if it delegates to measured-state ingest; do not use occupancy defaults.

---

## 4. UI contracts (UI team)

- Authority tabs: **Monitor**, **CV Monitor**, **Predict**, **Decide** for Phase 1; Phase 3 may merge CV into Monitor but do not remove required CV functionality.
- Show provenance badges: LIVE / CACHED / HISTORICAL / SIMULATED / PROXY / UNCALIBRATED.
- Evaluation page (`#viewEvaluation`) reads `/api/evaluation/summary`; if unavailable, show “not measured”.
- No hardcoded metrics, no “ByteTrack/CoreML/15m/calibrated” unless the backend says so.
- Keep the 1280/1440/1920 responsive behavior and zero console errors.

---

## 5. Write scopes

| Workstream | Files |
|---|---|
| CV | `traffic_system/computer_vision/`, `models/uvh26/`, `scripts/eval_cv.py`, `data/cv/` |
| ML | `traffic_system/core/measurement.py`, `traffic_system/live/bridge.py`, `traffic_system/core/traffic_physics.py`, `traffic_system/models/predictor.py` |
| UI | `app/static/` + generated `public/` |
| Repo | `tests/`, `pytest.ini`, `requirements.txt`, `Dockerfile`, `.dockerignore`, `.gitignore`, `.github/`, `vercel.json`, `render.yaml` |
| Lead | `app/server.py`, `app/routes/vision_routes.py`, `docs/`, `README.md`, `PROJECT_STRUCTURE.md` |

Coordinate before crossing scopes. Tests must use the isolated runtime state in `tests/conftest.py`.

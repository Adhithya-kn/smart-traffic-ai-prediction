# S-Tier Traffic Computer Vision & Vehicle Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the local video analytics pipeline into an S-Tier production system featuring Kalman-filtered ByteTrack association, arbitrary directional vector tripwires, polygonal counting zones, domain-adapted vehicle classification (including Auto-Rickshaws and Indo-HCM PCU weights), camera-specific ground-plane speed calibration, and per-vehicle exportable passage telemetry.

**Architecture:**
1. **Geometry & Spatial Kinematics (`traffic_system/computer_vision/geometry.py`)**: Vector 2D cross-product line-crossing detection (`Tripwire`) and ray-casting point-in-polygon spatial containment (`CountingZone`).
2. **Robust Multi-Object Tracking (`traffic_system/computer_vision/bytetrack.py` & `tracker.py`)**: ByteTrack two-stage association powered by an 8-state Kalman Filter ($x, y, a, h, v_x, v_y, v_a, v_h$) tracking both high- and low-confidence detections to eliminate ID churn in stop-and-go congestion.
3. **Domain Class Adaptation & Counting (`traffic_system/computer_vision/vehicle_counter.py` & `detector.py`)**: Multi-tripwire passage accumulation, Indian mixed traffic domain classification (Cars, Motorcycles, Auto-Rickshaws, Buses, Trucks, Bicycles, LCVs), and Indo-HCM PCU flow modeling.
4. **End-to-End Pipeline & Reporting (`video_processor.py`, `vision_routes.py`, `app.js`)**: Real-time HUD overlay rendering for angled tripwires, passage event logging, and RESTful CSV/JSON telemetry export endpoints.

**Tech Stack:** Python 3.14, Ultralytics YOLO11, PyTorch 2.15 (Apple Silicon MPS / CPU), OpenCV 5.0, NumPy, pytest.
**Spec Reference:** Codebase audit & capability evaluation from session `dfd69912-4bba-43f4-9841-925f3c195fde`.

---

## Global Constraints
- **Pure Local Execution**: Zero external cloud CV dependencies. Runs locally on Apple Silicon MPS or multi-core CPU.
- **Cryptographic & Durability Standards**: Two-phase atomic file writes (`temp_output` $\to$ `final_output`), strict input validation, POSIX fsync.
- **Genuine Inference Invariant**: Zero synthetic bounding boxes in standard production mode; clean empty detection returns on empty frames.
- **Runtime Safety**: PyTorch initialized before OpenMP/XGBoost imports to prevent Apple Silicon dynamic linker collisions.
- **Zero Regression**: All existing 41 tests across `tests/test_vision*.py` must pass continuously throughout implementation.

---

## Review Focus
1. **Centroid on Exact Tripwire Line**: Cross-product evaluates to zero without division-by-zero errors or missing crossing events.
2. **Directional Flow Discrimination**: Vehicles crossing in the wrong direction ($B \to A$) must not increment an $A \to B$ unidirectional tripwire counter.
3. **Stop-and-Go Queue Occlusion**: A vehicle stationary or occluded behind a bus for 15 frames must preserve its unique `track_id` upon re-emergence.
4. **Indian Traffic Auto-Rickshaw Classification**: Three-wheeler detection handling via dedicated aspect-ratio/class mapping ensuring non-car classification.
5. **Memory Leakage Prevention**: Periodic cache purging (`torch.mps.empty_cache()`) during long video analysis ($> 3000$ frames).

---

## Task Decomposition

### Task 1: 2D Spatial Vector Geometry Engine (Tripwires & Polygonal Zones)

**Files:**
- Create: `traffic_system/computer_vision/geometry.py`
- Test: `tests/test_cv_geometry.py`

**Interfaces:**
- Produces:
  - `class Point2D(NamedTuple)`: `x: float, y: float`
  - `class VectorTripwire`:
    - `__init__(name: str, p1: Tuple[float, float], p2: Tuple[float, float], allowed_direction: Optional[str] = "FORWARD")`
    - `check_crossing(prev_pt: Tuple[float, float], curr_pt: Tuple[float, float]) -> Optional[str]` (returns `"FORWARD"`, `"REVERSE"`, or `None`)
  - `class PolygonalZone`:
    - `__init__(name: str, polygon_points: List[Tuple[float, float]])`
    - `contains_point(pt: Tuple[float, float]) -> bool`

- [ ] **Step 1: Write the failing unit tests for geometry and line crossing**
  Write tests in `tests/test_cv_geometry.py` testing forward crossing, reverse crossing, non-crossing, collinear points, and polygon containment.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_cv_geometry.py -v`
  Expected: FAIL (`ModuleNotFoundError: No module named 'traffic_system.computer_vision.geometry'`)

- [ ] **Step 3: Implement `geometry.py` with 2D cross-product line intersection and ray-casting**
  Implement vector math using cross product sign transitions and ray-casting algorithm for point-in-polygon.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_cv_geometry.py -v`
  Expected: PASS (all tests pass in `< 0.2s`).

- [ ] **Step 5: Commit changes**
  Run:
  ```bash
  git add traffic_system/computer_vision/geometry.py tests/test_cv_geometry.py
  git commit -m "feat(cv): add 2d vector tripwire and polygonal zone geometry engine"
  ```

---

### Task 2: Kalman Filter & ByteTrack Multi-Object Association Engine

**Files:**
- Create: `traffic_system/computer_vision/kalman_filter.py`
- Create: `traffic_system/computer_vision/bytetrack.py`
- Modify: `traffic_system/computer_vision/tracker.py:1-278`
- Test: `tests/test_bytetrack.py`

**Interfaces:**
- Consumes: `DetectionBox` from `traffic_system.computer_vision.schemas`
- Produces:
  - `class KalmanBoxFilter`: 8-state linear Kalman Filter for bounding box tracking $[x, y, a, h, \dot{x}, \dot{y}, \dot{a}, \dot{h}]$
  - `class ByteTrackVehicleTracker`:
    - `update(detections: List[DetectionBox], frame_idx: int, fps: float) -> List[DetectionBox]`
    - Preserves IDs through high-low confidence two-stage matching and Kalman covariance propagation.
  - Backward-compatible `VehicleTracker` facade in `tracker.py` pointing to the upgraded tracker.

- [ ] **Step 1: Write the failing test for Kalman filter state prediction and ByteTrack association**
  Create `tests/test_bytetrack.py` verifying state prediction, IoU distance matrix association, occlusion recovery across 15 dropped frames, and low-confidence detection matching.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_bytetrack.py -v`
  Expected: FAIL (`ModuleNotFoundError: No module named 'traffic_system.computer_vision.kalman_filter'`)

- [ ] **Step 3: Implement `KalmanBoxFilter` and `ByteTrackVehicleTracker`**
  - Implement 8-state Kalman Filter with constant velocity model and dynamic measurement uncertainty based on box height.
  - Implement ByteTrack two-stage matching:
    - Stage 1: Associate high-confidence detections ($conf \ge 0.50$) with tracked kalman predictions.
    - Stage 2: Associate remaining unmatched tracks with low-confidence detections ($0.15 \le conf < 0.50$).
    - Stage 3: Project lost tracks forward using Kalman filter for up to 30 frames.
  - Wire `VehicleTracker` in `tracker.py` to utilize `ByteTrackVehicleTracker`.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_bytetrack.py tests/test_cv_improvements.py -v`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  Run:
  ```bash
  git add traffic_system/computer_vision/kalman_filter.py traffic_system/computer_vision/bytetrack.py traffic_system/computer_vision/tracker.py tests/test_bytetrack.py
  git commit -m "feat(cv): integrate kalman filter and bytetrack multi-object association"
  ```

---

### Task 3: Arbitrary Directional Tripwire Vehicle Counter

**Files:**
- Modify: `traffic_system/computer_vision/schemas.py:1-120`
- Modify: `traffic_system/computer_vision/vehicle_counter.py:1-300`
- Test: `tests/test_tripwire_counter.py`

**Interfaces:**
- Consumes: `VectorTripwire` and `PolygonalZone` from `geometry.py`, `DetectionBox` from `schemas.py`
- Produces:
  - `class VehiclePassageEvent(BaseModel / NamedTuple)`:
    `passage_id: str, track_id: int, class_name: str, tripwire_name: str, direction: str, timestamp_sec: float, speed_kmh: float, frame_idx: int`
  - Upgraded `VehicleCounter`:
    - `add_tripwire(tripwire: VectorTripwire)`
    - `add_zone(zone: PolygonalZone)`
    - `update(detections, timestamp_sec, frame_width, frame_height) -> Dict[str, Any]`
    - `get_passage_events() -> List[Dict[str, Any]]`
    - Maintains backward-compatible `cumulative_classes`, `current_frame_classes`, and route transits.

- [ ] **Step 1: Write failing test for tripwire vehicle counting and passage logging**
  Write tests in `tests/test_tripwire_counter.py` testing vertical, horizontal, and diagonal tripwires, forward/reverse crossing separation, and passage event generation.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_tripwire_counter.py -v`
  Expected: FAIL

- [ ] **Step 3: Update `schemas.py` and implement multi-tripwire counter in `vehicle_counter.py`**
  - Add `TripwireDefinition` and `VehiclePassageEvent` schemas.
  - Refactor `VehicleCounter` to store trajectory histories and check crossings across all registered tripwires using vector cross-products.
  - Log completed passage events with millisecond timestamps and estimated speeds.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_tripwire_counter.py tests/test_cv_improvements.py -v`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  Run:
  ```bash
  git add traffic_system/computer_vision/schemas.py traffic_system/computer_vision/vehicle_counter.py tests/test_tripwire_counter.py
  git commit -m "feat(cv): implement configurable vector tripwire vehicle counter and passage events"
  ```

---

### Task 4: Indian Mixed Traffic Domain Classes & PCU Normalization

**Files:**
- Modify: `traffic_system/computer_vision/detector.py:20-50`
- Modify: `traffic_system/computer_vision/pcu_converter.py:1-120`
- Test: `tests/test_domain_classes.py`

**Interfaces:**
- Consumes: Ultralytics YOLO predictions
- Produces:
  - Canonical class taxonomy including `auto_rickshaw` ($PCU = 0.80$) and `lcv` ($PCU = 1.50$).
  - Intelligent geometric rule mapper for COCO weights: In urban Indian CCTV, vehicles classified with borderline car/motorcycle confidence and characteristic 3-wheeler aspect ratio ($W/H \approx 0.75 - 0.95$ and area $< 0.45 \times \text{car\_area}$) are tagged as `auto_rickshaw`.
  - Indo-HCM calculation updated with `auto_rickshaw` and `lcv`.

- [ ] **Step 1: Write failing test for domain class expansion and PCU calculations**
  Write tests in `tests/test_domain_classes.py` testing `auto_rickshaw` recognition, PCU conversion, and class-specific direction breakdown.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_domain_classes.py -v`
  Expected: FAIL

- [ ] **Step 3: Implement domain class mapping in `detector.py` and update `pcu_converter.py`**
  Add `auto_rickshaw` and `lcv` to supported vehicle classes, configure Indo-HCM PCU equivalencies ($0.80$ for autos, $1.50$ for LCVs), and update detector class remapping logic.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_domain_classes.py -v`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  Run:
  ```bash
  git add traffic_system/computer_vision/detector.py traffic_system/computer_vision/pcu_converter.py tests/test_domain_classes.py
  git commit -m "feat(cv): add auto-rickshaw and lcv domain classes with indo-hcm factors"
  ```

---

### Task 5: Video Pipeline Integration & Dynamic HUD Overlay

**Files:**
- Modify: `traffic_system/computer_vision/video_processor.py:1-656`
- Test: `tests/test_video_pipeline_enhancements.py`

**Interfaces:**
- Consumes: Configured tripwires, ByteTrack tracker, and updated VehicleCounter.
- Produces:
  - Output video with annotated vector tripwires (pulsing green on vehicle crossing), vehicle trajectory trails, and per-tripwire crossing stats.
  - `passage_events` and `tripwire_telemetry` included in job results dictionary.

- [ ] **Step 1: Write failing test for enhanced video processor output**
  Create `tests/test_video_pipeline_enhancements.py` testing video processing with custom tripwires, verifying passage events count and output video integrity.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_video_pipeline_enhancements.py -v`
  Expected: FAIL

- [ ] **Step 3: Update `VideoProcessor` in `video_processor.py`**
  - Integrate configurable tripwires from camera config or job parameters.
  - Draw dynamic tripwires with name labels and crossing event counters.
  - Collect `passage_events` in the returned results payload.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_video_pipeline_enhancements.py -v`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  Run:
  ```bash
  git add traffic_system/computer_vision/video_processor.py tests/test_video_pipeline_enhancements.py
  git commit -m "feat(cv): integrate vector tripwires and passage telemetry into video processor"
  ```

---

### Task 6: Telemetry CSV/JSON Export API & Web Interface Controls

**Files:**
- Modify: `app/routes/vision_routes.py:1-681`
- Modify: `app/static/index.html:615-770`
- Modify: `app/static/app.js:4200-4350`
- Test: `tests/test_vision_export_api.py`

**Interfaces:**
- Endpoints:
  - `GET /api/vision/export/{job_id}?format=csv` $\to$ Returns downloadable CSV of all vehicle passage events.
  - `GET /api/vision/export/{job_id}?format=json` $\to$ Returns full JSON telemetry report.
  - `POST /api/vision/process` updated to accept custom tripwire coordinates in request payload.
- Frontend:
  - Adds "Export CSV Passage Log" and "Export JSON Report" buttons in the vision intelligence sidecar card.

- [ ] **Step 1: Write failing test for export API endpoint**
  Create `tests/test_vision_export_api.py` verifying authentication, CSV formatting, content-disposition header, and 404 on invalid job IDs.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_vision_export_api.py -v`
  Expected: FAIL

- [ ] **Step 3: Implement export handlers in `vision_routes.py` and UI elements in `index.html` & `app.js`**
  - Implement `handle_export_telemetry` supporting CSV streaming with standard headers (`passage_id,track_id,class,timestamp_sec,speed_kmh,tripwire,direction`).
  - Add download buttons in `index.html` and wire event listeners in `app.js`.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_vision_export_api.py -v`
  Expected: PASS

- [ ] **Step 5: Run full regression test suite**
  Run: `pytest -v`
  Expected: All existing and new tests pass (0 failures).

- [ ] **Step 6: Commit changes**
  Run:
  ```bash
  git add app/routes/vision_routes.py app/static/index.html app/static/app.js tests/test_vision_export_api.py
  git commit -m "feat(cv): add vehicle passage telemetry csv/json export api and ui buttons"
  ```

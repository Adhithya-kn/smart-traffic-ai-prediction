# Tri-Pillar Spatio-Temporal Heatmap: End-to-End Implementation Plan (Final)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cleanly retire obsolete, deprecated, and unphysical heatmap artifacts (Google `HeatmapLayer` removal fallback, crude `google.maps.Circle` discs, unphysical $k=714$ veh/km densities, pedestrian deceleration false alarms, and orphaned junction calculations) and replace them with a unified, high-performance, multi-channel Tri-Pillar Heatmap engine displaying forward-looking traffic prediction ($T_0 \to T_{+60m}$), pedestrian crowd dynamics & Fruin LOS, and interactive Webster signal-optimized junction chokepoints.

**Architecture:** A backend service ([`HeatmapService`](file:///Users/ak/Documents/Dp-01/traffic_system/live/heatmap_service.py) mounted at `GET /api/map/heatmap/v2`) aggregates XGBoost segment prediction probabilities, pedestrian/crowd telemetry, and [`JunctionService`](file:///Users/ak/Documents/Dp-01/traffic_system/junction/junction_service.py) queue/delay metrics across 4 discrete temporal horizons ($T_0, T_{+15m}, T_{+30m}, T_{+60m}$). A client-side continuous Gaussian Kernel Density Estimation canvas engine ([`HeatCanvasEngine`](file:///Users/ak/Documents/Dp-01/app/static/heat_canvas_engine.js)) renders smooth multi-channel heat surfaces on Google Maps and offline vector fallback, paired with an interactive tactile scrub bar and on-click Webster junction inspector HUD.

**Tech Stack:** Python 3.14, Ultralytics YOLO11n, XGBoost / Scikit-learn, Webster & Akcelik Signal Optimization (IRC:93), Google Maps JS API + HTML5 Canvas 2D Overlay, Vanilla JavaScript, Apple HIG Obsidian Design CSS.

**Spec:** [`docs/VISION.md`](file:///Users/ak/Documents/Dp-01/docs/VISION.md) and Research Audit.

---

## Global Constraints & Removal Targets

1. **What Must Be Explicitly Removed / Replaced**:
   - **REPLACE**: `google.maps.Circle` discs in `loadCongestionHeatmap()` ([`app.js:3400-3440`](file:///Users/ak/Documents/Dp-01/app/static/app.js#L3400-L3440)) with continuous Gaussian rasterization via `HeatCanvasEngine`.
   - **REMOVE**: Pedestrian tracks from vehicle deceleration and wrong-way incident detection in [`incident_detector.py`](file:///Users/ak/Documents/Dp-01/traffic_system/computer_vision/incident_detector.py), eliminating the 589 false alarms.
   - **REPLACE**: Unphysical $k = q / v$ math ($700+$ veh/km) with physically clamped density ($k \le 150 \text{ veh/km/lane}$).
   - **RECONNECT**: Orphaned [`JunctionService`](file:///Users/ak/Documents/Dp-01/traffic_system/junction/junction_service.py) to the frontend map, replacing static cyan pins with dynamic queue and Webster cycle glyphs.
   - **FORWARD**: Legacy `/api/map/heatmap` to maintain backward compatibility while delegating to the new multi-channel engine.

2. **UI & Aesthetic Mandate**:
   - Deep neutral obsidian palette (`#07080a`), Apple HIG materials, spring physics `cubic-bezier(0.16, 1, 0.3, 1)`, tactile press scale `scale(0.965)`, and tabular figures.

3. **Data Integrity & Traceability**:
   - Explicit provenance tags on all data packets: `PROVENANCE_LIVE`, `PROVENANCE_PREDICTED`, `PROVENANCE_HISTORICAL_BASELINE`, or `PROVENANCE_SIMULATED`.

4. **Testing & Static Parity**:
   - Fast suite (`pytest -m "not integration"`) must maintain 100% pass rate (213+ passed).
   - `python3 scripts/sync_static.py --check` must confirm `app/static/` $\equiv$ `public/`.

---

## Review Focus

1. **Division by Zero and Density Clamping**: Guard against $v < 5.0 \text{ km/h}$ to prevent infinite densities; enforce hard upper bound $k_{jam} \le 150.0 \text{ veh/km/lane}$.
2. **Temporal Probability Interpolation**: For intermediate horizons ($T_{+15m}, T_{+30m}$), interpolate class probability distributions smoothly between observed $T_0$ and XGBoost $T_{+60m}$ forecast to avoid jarring step-function jumps.
3. **Pedestrian Kinematic Isolation**: Guarantee that `DetectionBox` with `class_name == "pedestrian"` is tracked for crowd density but excluded from vehicle incident pipelines.
4. **Offline / Sandboxed Fallback Resilience**: Ensure `HeatCanvasEngine` operates without errors when Google Maps fails to load or lacks an API key, rendering directly on the vector canvas.
5. **Timeline Scrubbing Concurrency**: Rapid slider scrubbing must abort in-flight fetch/render passes via `AbortController` and `requestAnimationFrame` cancellation.

---

## Task Decomposition

### Task 1: Backend Tri-Pillar Heatmap Engine & Multi-Channel API (`/api/map/heatmap/v2`)

**Files:**
- Create: `traffic_system/live/heatmap_service.py`
- Modify: `app/server.py:810-830`
- Modify: `traffic_system/live/bridge.py:646-701`
- Test: `tests/test_heatmap_v2_service.py`

**Interfaces:**
- Consumes:
  - `TrafficPredictor.predict_segment(features: Dict[str, Any]) -> Tuple[str, Dict[str, float]]`
  - `JunctionService.get_junction_telemetry(road_id: str, hour: int, minute: int) -> Dict[str, Any]`
  - `EventManager.find_active_events(road_id: str) -> List[Dict[str, Any]]`
  - `ROAD_REGISTRY`, `CORRIDOR_GEO_REGISTRY` from `traffic_system/core/road_registry.py`
- Produces:
  - `HeatmapService.get_tri_pillar_heatmap(horizon_minutes: int, channel: str) -> Dict[str, Any]`
  - REST endpoint `GET /api/map/heatmap/v2?horizon=0|15|30|60&channel=all|traffic|crowd|junctions`
  - Refactored `GET /api/map/heatmap` delegating to `HeatmapService`

- [ ] **Step 1: Write failing unit tests for `HeatmapService` and `/api/map/heatmap/v2`**

```python
# tests/test_heatmap_v2_service.py
import pytest
from traffic_system.live.heatmap_service import HeatmapService
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager
from traffic_system.junction.junction_service import JunctionService

def test_heatmap_v2_tri_pillar_payload():
    pred = TrafficPredictor()
    pred.load_artifacts()
    ev_mgr = EventManager()
    jnc_svc = JunctionService(pred, ev_mgr)
    svc = HeatmapService(pred, jnc_svc, ev_mgr)

    # Test complete multi-channel payload at horizon=60m
    data = svc.get_tri_pillar_heatmap(horizon_minutes=60, channel="all")
    assert data["status"] == "success"
    assert data["horizon_minutes"] == 60
    assert "traffic_layer" in data
    assert "crowd_layer" in data
    assert "junction_layer" in data
    assert len(data["traffic_layer"]) >= 24
    assert len(data["junction_layer"]) >= 24
    assert len(data["crowd_layer"]) >= 6

    # Verify physical density bounds on traffic segments
    for corridor in data["traffic_layer"]:
        for pt in corridor["sub_segments"]:
            assert 0.0 <= pt["weight"] <= 1.0
            assert pt["density_k"] <= 150.0  # Physical jam density clamp
            assert pt["predicted_los"] in ["Low", "Moderate", "High", "Severe"]
            assert "prob_dist" in pt
            assert len(pt["prob_dist"]) == 4

    # Verify junction Webster metrics
    silk_board = next((j for j in data["junction_layer"] if j["junction_id"] == "INT_BLR_11"), data["junction_layer"][0])
    assert silk_board["queue_meters"] > 0
    assert silk_board["control_delay_sec"] > 0
    assert silk_board["webster_cycle_sec"] >= 45.0
    assert silk_board["green_split_ns_sec"] > 0

    # Verify crowd metrics and Fruin LOS
    majestic = next((c for c in data["crowd_layer"] if "Majestic" in c["name"]), data["crowd_layer"][0])
    assert majestic["ped_density_sqm"] > 0
    assert majestic["fruin_los"].startswith("LOS")
    assert 0.0 <= majestic["vru_conflict_index"] <= 1.0

def test_heatmap_v2_horizon_transition():
    pred = TrafficPredictor()
    pred.load_artifacts()
    svc = HeatmapService(pred, JunctionService(pred, EventManager()), EventManager())

    t0_data = svc.get_tri_pillar_heatmap(horizon_minutes=0, channel="traffic")
    t60_data = svc.get_tri_pillar_heatmap(horizon_minutes=60, channel="traffic")
    assert t0_data["horizon_minutes"] == 0
    assert t60_data["horizon_minutes"] == 60
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_heatmap_v2_service.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'traffic_system.live.heatmap_service'`).

- [ ] **Step 3: Implement `HeatmapService` in `traffic_system/live/heatmap_service.py`**

Implement class `HeatmapService`:
1. `__init__(self, predictor, junction_service, event_manager)`: stores shared components.
2. `_interpolate_polyline(self, coords: List[List[float]], step_count: int = 4) -> List[List[float]]`: generates sub-segments along each corridor polyline.
3. `_compute_traffic_layer(self, horizon_minutes: int) -> List[Dict[str, Any]]`:
   - Evaluates each corridor's current state and XGBoost next-hour predictions.
   - For $T_0$: uses observed LOS.
   - For $T_{+60m}$: uses predicted class probabilities $P(\text{Severe}), P(\text{High}), P(\text{Moderate}), P(\text{Low})$.
   - For $T_{+15m}, T_{+30m}$: computes linearly interpolated probability vector:
     $$\mathbf{P}(t) = \left(1 - \frac{t}{60}\right) \mathbf{P}(0) + \left(\frac{t}{60}\right) \mathbf{P}(60)$$
   - Computes intensity weight:
     $$W = 1.0 \cdot P(\text{Severe}) + 0.75 \cdot P(\text{High}) + 0.45 \cdot P(\text{Moderate}) + 0.15 \cdot P(\text{Low})$$
   - Computes physically clamped density $k = \min(150.0 \times \text{lanes}, \text{vol} / \max(5.0, \text{spd}))$.
4. `_compute_crowd_layer(self, hour: int) -> List[Dict[str, Any]]`:
   - 6 canonical high-footfall Bengaluru hubs (Majestic, Silk Board, Indiranagar, Brigade Road, Electronic City, Hebbal).
   - Area, pedestrian count, Fruin walkway LOS (A–F), and VRU conflict index $I_{VRU} = \min(1.0, \rho_{ped} \times (v_{veh}/50.0)^2)$.
5. `_compute_junction_layer(self, hour: int, minute: int) -> List[Dict[str, Any]]`:
   - Queries `junction_service.get_junction_telemetry` for all 24 corridors.
   - Extracts queue meters, control delay, HCM LOS, Webster cycle $C_0$, NS/EW green splits, and spillback risk.
6. `get_tri_pillar_heatmap(self, horizon_minutes: int = 0, channel: str = "all") -> Dict[str, Any]`.

- [ ] **Step 4: Wire endpoints in `app/server.py` and refactor legacy `/api/map/heatmap`**

In `app/server.py`:
1. In `init_services`: instantiate `cls.heatmap_service = HeatmapService(cls.predictor, cls.junction_service, cls.event_mgr)`.
2. Under `do_GET`:
   ```python
   elif path == "/api/map/heatmap/v2":
       horizon = int(query_params.get("horizon", [0])[0])
       channel = str(query_params.get("channel", ["all"])[0])
       data = self.heatmap_service.get_tri_pillar_heatmap(horizon_minutes=horizon, channel=channel)
       return self._send_json(200, data)
   elif path == "/api/map/heatmap":
       # Backward-compatible delegate returning flattened points with clamped physical density
       data = self.heatmap_service.get_legacy_points_projection()
       return self._send_json(200, data)
   ```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_heatmap_v2_service.py -v`
Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add traffic_system/live/heatmap_service.py app/server.py tests/test_heatmap_v2_service.py
git commit -m "feat(heatmap): implement Tri-Pillar HeatmapService and /api/map/heatmap/v2"
```

---

### Task 2: CV Pedestrian Crowd Telemetry & Incident False-Positive Noise Filter

**Files:**
- Modify: `traffic_system/computer_vision/incident_detector.py:150-176`
- Modify: `traffic_system/computer_vision/vehicle_counter.py:90-140`
- Modify: `traffic_system/core/measurement.py:50-75`
- Test: `tests/test_pedestrian_crowd_and_incident_filter.py`

**Interfaces:**
- Consumes:
  - `DetectionBox` from `traffic_system/computer_vision/schemas.py`
  - `IncidentDetector.update(...)`
- Produces:
  - Noise-filtered `IncidentDetector.update` ignoring pedestrians for vehicle deceleration & wrong-way alarms.
  - Clamped vehicle deceleration ($a \ge -10.0 \text{ m/s}^2$).
  - `VehicleCounter.get_crowd_density(roi_area_sqm: float) -> Dict[str, Any]`

- [ ] **Step 1: Write failing tests for pedestrian noise filtering and crowd tracking**

```python
# tests/test_pedestrian_crowd_and_incident_filter.py
from traffic_system.computer_vision.incident_detector import IncidentDetector
from traffic_system.computer_vision.vehicle_counter import VehicleCounter
from traffic_system.computer_vision.schemas import DetectionBox

def test_pedestrians_excluded_from_deceleration_and_wrong_way_incidents():
    detector = IncidentDetector()
    ped_box = DetectionBox(x1=10, y1=10, x2=20, y2=40, confidence=0.85, class_id=0, class_name="pedestrian")
    
    # Simulate track moving at high speed then stopping abruptly
    detector.update(track_id=1, box=ped_box, speed_kmh=25.0, frame_idx=0, fps=30.0)
    incidents = detector.update(track_id=1, box=ped_box, speed_kmh=0.0, frame_idx=1, fps=30.0)
    
    # MUST NOT generate deceleration incident for pedestrian
    assert len(incidents) == 0

def test_vehicle_deceleration_clamped_to_physical_limits():
    detector = IncidentDetector()
    car_box = DetectionBox(x1=10, y1=10, x2=50, y2=50, confidence=0.9, class_id=2, class_name="car")
    
    # 60 km/h to 0 in 1 frame (impossible -350 m/s^2)
    detector.update(track_id=2, box=car_box, speed_kmh=60.0, frame_idx=0, fps=30.0)
    incidents = detector.update(track_id=2, box=car_box, speed_kmh=0.0, frame_idx=1, fps=30.0)
    
    assert len(incidents) == 1
    assert incidents[0]["type"] == "INCIDENT_RAPID_DECELERATION"
    assert incidents[0]["deceleration_mps2"] >= -10.0  # Physically clamped

def test_vehicle_counter_accumulates_pedestrian_crowd_metrics():
    counter = VehicleCounter()
    peds = [
        DetectionBox(x1=10, y1=10, x2=20, y2=40, confidence=0.85, class_id=0, class_name="pedestrian"),
        DetectionBox(x1=30, y1=10, x2=40, y2=40, confidence=0.85, class_id=0, class_name="pedestrian")
    ]
    counter.update_pedestrian_counts(peds)
    crowd = counter.get_crowd_density(roi_area_sqm=50.0)
    assert crowd["pedestrian_count"] == 2
    assert crowd["density_sqm"] == 0.04
    assert crowd["fruin_los"] == "LOS A"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pedestrian_crowd_and_incident_filter.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement pedestrian filtering and physical clamping**

In `traffic_system/computer_vision/incident_detector.py`:
1. At the beginning of heading and deceleration evaluations, check `if box.class_name == "pedestrian": return []`.
2. In deceleration calculation, clamp `accel_mps2 = max(-10.0, accel_mps2)`.
3. In `vehicle_counter.py`:
   - Implement `update_pedestrian_counts(self, detections: List[DetectionBox])`.
   - Implement `get_crowd_density(self, roi_area_sqm: float = 100.0) -> Dict[str, Any]` returning Fruin LOS.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pedestrian_crowd_and_incident_filter.py -v`
Expected: PASS.

- [ ] **Step 5: Verify fast test suite passes with zero regressions**

Run: `pytest -m "not integration"`
Expected: 215+ passed.

- [ ] **Step 6: Commit Task 2**

```bash
git add traffic_system/computer_vision/incident_detector.py traffic_system/computer_vision/vehicle_counter.py tests/test_pedestrian_crowd_and_incident_filter.py
git commit -m "fix(cv): exclude pedestrians from vehicle incidents and add crowd density estimation"
```

---

### Task 3: Continuous Gaussian Canvas Heatmap Overlay Engine (`HeatCanvasEngine`)

**Files:**
- Create: `app/static/heat_canvas_engine.js`
- Modify: `app/static/index.html` (include `<script src="heat_canvas_engine.js?v=2.6"></script>`)
- Sync: `python3 scripts/sync_static.py`
- Test: `tests/test_heat_canvas_engine_static.py`

**Interfaces:**
- Produces:
  - `class HeatCanvasEngine(options)`
  - Methods:
    - `attachToGoogleMap(gMap)`: mounts custom `google.maps.OverlayView`.
    - `attachToVectorCanvas(canvasEl)`: mounts to fallback 2D vector canvas.
    - `setData(heatmapV2Payload)`: updates multi-channel points.
    - `setHorizon(minutes)`: updates active horizon ($0, 15, 30, 60$).
    - `setLayers({traffic, crowd, junctions})`: toggles channel visibility.
    - `render()`: executes 2D Gaussian kernel density rasterization on offscreen canvas.

- [ ] **Step 1: Write static asset verification test**

```python
# tests/test_heat_canvas_engine_static.py
from pathlib import Path

def test_heat_canvas_engine_exists_and_in_index():
    js_file = Path("app/static/heat_canvas_engine.js")
    assert js_file.exists(), "heat_canvas_engine.js must exist"
    
    content = js_file.read_text(encoding="utf-8")
    assert "class HeatCanvasEngine" in content
    assert "renderGaussianKernel" in content or "renderHeatmap" in content
    
    index_html = Path("app/static/index.html").read_text(encoding="utf-8")
    assert "heat_canvas_engine.js" in index_html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_heat_canvas_engine_static.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `app/static/heat_canvas_engine.js`**

Implement `HeatCanvasEngine`:
1. Use offscreen `<canvas>` buffer for 2D Gaussian kernel density splatting ($A(r) = e^{-r^2 / (2\sigma^2)}$).
2. Colorize with 256-entry gradient LUT:
   - Traffic channel: Emerald `rgba(16, 185, 129)` $\to$ Amber `rgba(245, 158, 11)` $\to$ Orange `rgba(249, 115, 22)` $\to$ Crimson `rgba(239, 68, 68)`.
   - Crowd channel: Electric Cyan `rgba(6, 182, 212)` $\to$ Deep Indigo `rgba(99, 102, 241)` $\to$ Magenta `rgba(217, 70, 239)`.
3. Subclass `google.maps.OverlayView` to project lat/lng to screen coordinates without `google.maps.Circle` discs.
4. Fallback gracefully to `attachToVectorCanvas()` when Google Maps is unavailable.

- [ ] **Step 4: Update `app/static/index.html` and synchronize assets**

Include `<script src="heat_canvas_engine.js?v=2.6"></script>` in `app/static/index.html`.
Run `python3 scripts/sync_static.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_heat_canvas_engine_static.py -v`
Expected: PASS.
Run: `python3 scripts/sync_static.py --check`
Expected: `[OK] All static assets in public/ are in sync with app/static/`.

- [ ] **Step 6: Commit Task 3**

```bash
git add app/static/heat_canvas_engine.js app/static/index.html public/ tests/test_heat_canvas_engine_static.py
git commit -m "feat(frontend): build continuous Gaussian HeatCanvasEngine overlay"
```

---

### Task 4: Interactive Junction Chokepoint Glyphs & Live Webster Advisory HUD

**Files:**
- Modify: `app/static/app.js:3440-3490` (and mirror `public/app.js`)
- Modify: `app/static/index.html:1395-1440` (and mirror `public/index.html`)
- Modify: `app/static/styles.css:4490-4550` (and mirror `public/styles.css`)
- Test: `tests/test_junction_overlay_api.py`

**Interfaces:**
- Consumes:
  - `data.junction_layer` from `/api/map/heatmap/v2`
- Produces:
  - Concentric junction glyphs on map (queue length outer ring + HCM LOS inner core + Webster cycle badge).
  - Click handler opening `#junctionInspectorFlyout` with Webster splits and delay savings.

- [ ] **Step 1: Write API contract test for junction layer integration**

```python
# tests/test_junction_overlay_api.py
import pytest
from traffic_system.live.heatmap_service import HeatmapService
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager
from traffic_system.junction.junction_service import JunctionService

def test_junction_layer_payload_has_webster_advisories():
    pred = TrafficPredictor()
    pred.load_artifacts()
    ev = EventManager()
    jnc = JunctionService(pred, ev)
    svc = HeatmapService(pred, jnc, ev)
    
    data = svc.get_tri_pillar_heatmap(horizon_minutes=0, channel="junctions")
    junctions = data.get("junction_layer", [])
    assert len(junctions) >= 24
    
    silk_board = next((j for j in junctions if j["junction_id"] == "INT_BLR_11"), junctions[0])
    assert silk_board["queue_meters"] > 0
    assert silk_board["control_delay_sec"] > 0
    assert silk_board["webster_cycle_sec"] >= 45.0
    assert "green_split_ns_sec" in silk_board
    assert "green_split_ew_sec" in silk_board
    assert "spillback_risk" in silk_board
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_junction_overlay_api.py -v`
Expected: PASS.

- [ ] **Step 3: Implement dynamic junction glyphs and inspector HUD in frontend**

In `app/static/app.js`:
1. In `loadCorridorJunctionPins()`, bind to `data.junction_layer`.
2. Draw custom concentric marker icons:
   - Outer glow radius scaled to queue meters ($0\text{--}300\text{ m}$).
   - Inner color matching HCM Level of Service (Green, Amber, Orange, Red).
   - Label with Webster cycle time (e.g. `135s`).
3. Wire pin click to `openJunctionInspectorModal(junctionData)`:
   - Renders Webster cycle $C_0$, phase green splits ($g_{NS}, g_{EW}$), queue length in meters, control delay, and spillback risk in `#junctionInspectorFlyout`.

In `app/static/index.html` & `app/static/styles.css`:
- Add `#junctionInspectorFlyout` markup and Apple HIG glassmorphic styling.

- [ ] **Step 4: Sync assets and verify**

Run: `python3 scripts/sync_static.py`
Run: `python3 scripts/sync_static.py --check`
Expected: `[OK] All static assets in public/ are in sync with app/static/`.

- [ ] **Step 5: Commit Task 4**

```bash
git add app/static/app.js app/static/index.html app/static/styles.css public/ tests/test_junction_overlay_api.py
git commit -m "feat(junctions): render dynamic chokepoint glyphs and live Webster signal inspector"
```

---

### Task 5: Spatio-Temporal Timeline Scrub Bar & Compact Tactical HUD

**Files:**
- Modify: `app/static/index.html:1340-1480` (and mirror `public/index.html`)
- Modify: `app/static/app.js:3260-3440` (and mirror `public/app.js`)
- Modify: `app/static/styles.css:4490-4550` (and mirror `public/styles.css`)
- Test: `tests/test_heatmap_ui_controls.py`

**Interfaces:**
- Produces:
  - Timeline Scrub Bar with 4 discrete snap points: `T₀ (Live)`, `+15 min`, `+30 min`, `+60 min`.
  - Layer visibility switches: `[✓] Traffic Forecast`, `[✓] Crowd Density`, `[✓] Junction Chokepoints`.
  - Auto-play forecast cycle button `▶ Play Forecast`.
  - Tactical Summary HUD: Active Horizon, High/Severe corridor count, Peak Queue Junction, High-Risk Pedestrian Conflict points.

- [ ] **Step 1: Write frontend markup verification test**

```python
# tests/test_heatmap_ui_controls.py
from pathlib import Path

def test_index_html_has_tri_pillar_controls():
    content = Path("app/static/index.html").read_text(encoding="utf-8")
    assert "heatmapTimelineSlider" in content or "heatmapTimeScrubber" in content
    assert "btnToggleCrowd" in content
    assert "btnToggleJunctions" in content
    assert "btnPlayForecast" in content
    assert "tacticalHeatmapHud" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_heatmap_ui_controls.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement tactile scrub bar, layer switches, and tactical HUD**

In `app/static/index.html`:
1. Insert `#heatmapTimelineBar` above the map canvas with 4 snap points: `Live T₀`, `+15 min`, `+30 min`, `+60 min (XGBoost)` and auto-play button.
2. In layer toggles, add `btnToggleCrowd` and `btnToggleJunctions`.
3. Insert `#tacticalHeatmapHud` floating card over the map displaying active horizon metrics.

In `app/static/app.js`:
- Implement `onTimelineScrub(val)`: queries `/api/map/heatmap/v2?horizon=${val}` and triggers `heatCanvasEngine.setHorizon(val)`.
- Implement `toggleForecastAnimation()`: intervals through $0 \to 15 \to 30 \to 60 \text{ min}$.
- Implement layer toggle callbacks updating `heatCanvasEngine.setLayers(...)`.

In `app/static/styles.css`:
- Add Apple HIG styles for `#heatmapTimelineBar`, `.obsidian-slider`, and `#tacticalHeatmapHud`.

- [ ] **Step 4: Sync assets and run tests**

Run: `python3 scripts/sync_static.py`
Run: `pytest tests/test_heatmap_ui_controls.py -v`
Expected: PASS.

- [ ] **Step 5: Run full test suite to guarantee zero regressions**

Run: `pytest -m "not integration"`
Expected: All 217+ tests pass.

- [ ] **Step 6: Commit Task 5**

```bash
git add app/static/index.html app/static/app.js app/static/styles.css public/ tests/test_heatmap_ui_controls.py
git commit -m "feat(ui): add timeline scrub controller, layer blend toggles, and tactical HUD"
```

---

## Final Verification Gates

1. **Backend Contract Verification**: `GET /api/map/heatmap/v2` returns verified traffic predictions, crowd densities, and junction queue metrics across all 4 temporal horizons ($0, 15, 30, 60\text{ min}$).
2. **Kinematic & Physical Verification**: Deceleration values are clamped ($\ge -10.0 \text{ m/s}^2$), and densities do not exceed $150.0 \text{ veh/km/lane}$. Pedestrian walking no longer triggers vehicle emergency braking incidents.
3. **Frontend Visual Verification**: The heatmap renders as a continuous Gaussian density field (no disjoint circles or deprecated Google HeatmapLayer errors) on both Google Maps and the Obsidian Vector Fallback.
4. **Interactive Junction Verification**: Clicking any junction pin displays real Webster signal timing plans ($C_0, g_{NS}, g_{EW}$) and approach queue lengths.
5. **Static Sync Parity**: `python3 scripts/sync_static.py --check` confirms 100% parity between `app/static/` and `public/`.
6. **Full Suite Green**: `pytest -m "not integration"` passes completely with zero failures.

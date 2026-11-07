# S+ Tier Humanized Traffic Map Decluttering & Architectural Streamlining Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the metropolitan Google Maps and vector canvas fallback interface into a humanized, zero-bloat, S+ tier traffic situational awareness and decision platform while preserving 100% of existing backend, vision, routing, and simulation functionalities.

**Architecture:** Mute non-traffic POIs via Google Maps styling JSON; eliminate micro-lane polygon meshes and synthetic radial canvas spiderwebs; consolidate 4 overlapping floating HUDs into a single luxury Obsidian slide-over inspector; humanize all corridor and junction terminology.

**Tech Stack:** Google Maps JavaScript API (v3), HTML5 Canvas 2D, Vanilla ES2022 JavaScript, Modern CSS3 with Apple HIG obsidian blur materials, Python 3.14 regression harness.

**Spec:** [`docs/superpowers/specs/2026-11-07-map-decluttering-spec.md`](file:///Users/ak/Documents/Dp-01/docs/superpowers/specs/2026-11-07-map-decluttering-spec.md)

---

## Global Constraints

- Zero modifications or removals to backend API endpoints (`app/server.py`, `traffic_system/`).
- 100% test pass rate maintained across `pytest tests/` (all 253 tests pass, 0 regressions).
- Backwards compatibility for all DOM IDs checked by tests (`#tacticalHeatmapHud`, `#hudActiveHorizon`, `#hudPeakQueueJnc`, `#hudVruRiskHub`, `#heatmapTimelineSlider`, `#btnToggleCrowd`, `#btnToggleCorridors`).
- Perfect parity between `app/static/` and `public/` via `python3 scripts/sync_static.py`.
- No raw database primary keys (`RD_BLR_xx`, `INT_BLR_xx`, UUIDs) shown as primary labels in user-facing surfaces.

## Review Focus

1. **Map Pan/Zoom Performance**: Ensure eliminating multi-polygon micro-lanes and canvas blurs restores buttery 60 FPS panning.
2. **Backwards Compatibility**: Ensure existing automated tests inspecting DOM elements continue to pass without error.
3. **Information Density**: Ensure current speed, free-flow delta, congestion level, and action buttons remain fully accessible in the unified inspector.
4. **Touch & Click Precision**: Ensure clicking a road polyline or junction pin cleanly opens the unified inspector and highlights the segment without jitter.
5. **Static Sync Parity**: Verify `scripts/sync_static.py --check` returns 0 exit code after every change.

---

### Task 1: Mute Non-Traffic POIs & Refine Obsidian Dark Google Maps Styling

**Files:**
- Modify: `app/static/app.js:2950-3025`
- Test: `tests/test_heatmap_ui_controls.py`

- [ ] **Step 1: Inspect `OBSIDIAN_DARK_MAP_STYLES` in `app/static/app.js`**
  Review existing stylers for `poi`, `road`, `water`, and `transit`.
- [ ] **Step 2: Add strict POI silencing rules**
  Update `OBSIDIAN_DARK_MAP_STYLES` to turn off all commercial, retail, business, medical, and school POIs:
  ```javascript
  {
    featureType: "poi",
    elementType: "all",
    stylers: [{ visibility: "off" }]
  },
  {
    featureType: "road",
    elementType: "geometry",
    stylers: [{ color: "#141923" }]
  },
  {
    featureType: "road",
    elementType: "labels.text.fill",
    stylers: [{ color: "#94a3b8" }]
  }
  ```
- [ ] **Step 3: Run static sync and check tests**
  ```bash
  python3 scripts/sync_static.py
  pytest tests/test_heatmap_ui_controls.py
  ```

---

### Task 2: Streamline Polylines & Eliminate Synthetic Radial Spiderwebs

**Files:**
- Modify: `app/static/app.js:2802-2850` (Polyline rendering)
- Modify: `app/static/app.js:3161-3260` (Vector fallback canvas)
- Test: `tests/test_heat_canvas_engine_static.py`

- [ ] **Step 1: Simplify road polyline representation**
  In `highlightMapCorridorPolyline` and `renderMapLaneRoute`, ensure each road renders as a single, high-contrast, physical centerline polyline with smooth caps (`strokeWeight: 6`, `strokeOpacity: 0.95`). Remove micro-lane sub-polygon slicing on macro view.
- [ ] **Step 2: Eliminate radial canvas spiderwebs**
  In `initVectorFallbackMap` (`app/static/app.js`), remove the loop that draws straight radial lines from screen center `(w/2, h/2)` to road nodes. Replace with direct connected arterial segments between actual junction points.
- [ ] **Step 3: Run static sync and verify canvas test**
  ```bash
  python3 scripts/sync_static.py
  pytest tests/test_heat_canvas_engine_static.py
  ```

---

### Task 3: Consolidate Overlapping Floating HUDs into Unified Map Inspector

**Files:**
- Modify: `app/static/index.html:937-1065`
- Modify: `app/static/styles.css:1200-1350`
- Modify: `app/static/app.js:2853-2940`
- Test: `tests/test_heatmap_ui_controls.py`

- [ ] **Step 1: Design unified inspector HTML structure in `app/static/index.html`**
  Consolidate `#heatmapCorridorFlyout`, `#junctionInspectorFlyout`, and the floating HUD elements into:
  1. A single non-intrusive floating status bar at the top: `#mapFloatingStatusBar` (containing existing IDs `#hudActiveHorizon`, `#hudPeakQueueJnc`, `#hudVruRiskHub`, `#tacticalHeatmapHud` cleanly nested and unobtrusive).
  2. A single slide-over contextual sheet on the right: `#unifiedMapInspector` with clean semantic sections for Corridor Speed, Signal Progression, and 1-Click Alternate Route Action.
- [ ] **Step 2: Add luxury Obsidian CSS styling in `app/static/styles.css`**
  Add styles for `#unifiedMapInspector`:
  - `position: absolute; right: 16px; top: 16px; width: 340px;`
  - `background: rgba(10, 14, 22, 0.94); backdrop-filter: blur(16px);`
  - `border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 12px;`
  - `transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;`
- [ ] **Step 3: Update opening/closing JavaScript handlers in `app/static/app.js`**
  Update `openHeatmapCorridorFlyout` and `openJunctionInspector` to populate the unified inspector sheet. Add listener to close the sheet when user pans or zooms the map canvas.
- [ ] **Step 4: Verify UI controls test suite**
  ```bash
  python3 scripts/sync_static.py
  pytest tests/test_heatmap_ui_controls.py
  ```

---

### Task 4: Humanize Roadway & Landmark Terminology

**Files:**
- Modify: `app/static/app.js:2853-2940`
- Test: `tests/test_road_registry.py`

- [ ] **Step 1: Replace raw DB keys with human landmarks**
  Ensure whenever a road is displayed in the UI (e.g. flyouts, HUD, toasts, list items), the primary heading is `corridor.road_name` (e.g. *"100 Feet Road"*) and subtitle is `"${corridor.city_zone} Sector • near ${corridor.intersection_name}"`.
  The internal identifier (e.g. `RD_BLR_01`) is moved to a discreet secondary monospace badge or dev metadata chip.
- [ ] **Step 2: Humanize delay and speed labels**
  Format speed as `${speed} km/h (Free-flow: ${ff} km/h)` and delay as `+${delay} min vs normal`.
- [ ] **Step 3: Test road registry**
  ```bash
  pytest tests/test_road_registry.py
  ```

---

### Task 5: End-to-End Regression Verification & Live Audit

**Files:**
- Verify: `tests/` (all test files)
- Verify: `scratch/test_e2e_sequential.py`
- Verify: `scripts/sync_static.py`

- [ ] **Step 1: Sync all static assets**
  ```bash
  python3 scripts/sync_static.py --check
  ```
- [ ] **Step 2: Run complete pytest suite**
  ```bash
  pytest tests/
  ```
  Confirm 253 passed, 4 skipped (100% pass rate).
- [ ] **Step 3: Run comprehensive e2e test suite against live server**
  ```bash
  python3 scratch/test_e2e_sequential.py
  ```
  Confirm 27 passed, 0 failed.

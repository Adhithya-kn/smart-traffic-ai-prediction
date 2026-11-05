# Audit Report: Smart Traffic AI (Dp-01)

**Date:** 2026-11-04
**Audit baseline:** git HEAD `db9134a` plus a worktree snapshot taken 18:15 IST
**Scope:** repository, CV pipeline, ML/data provenance, UI/API, tests, deployment
**Product direction:** [`VISION.md`](VISION.md)
**Official requirements:** [`requirements/378_Design Project Problem Statement_6_Rashmi Mothkur.docx`](requirements/378_Design%20Project%20Problem%20Statement_6_Rashmi%20Mothkur.docx)

> **Concurrency caveat:** during the audit a concurrent process with this repo open (Antigravity IDE / related agent) modified 15 tracked files and added 3 untracked entries between 18:17 and 18:23, including `app/server.py`, `app/static/*`, `tests/*`, `traffic_system/computer_vision/video_processor.py`, and a new 12.3MB `sample_north_east.mp4`; `Dataset/North-East.mp4` changed from 174MB to 55.3MB. The live server on 8081 was not restarted and was serving a mix of old/new static files. Findings below are pinned to the audit snapshot; re-verify line numbers after the worktree is frozen. The audit team did not modify the repository.

---

## 1. Verdict

**The project is a functional single-node capstone prototype (TRL 4), roughly 60–70% toward a solid demo/report. It is not production-grade, and it is not yet a computer-vision traffic-understanding system.**

- **CV measurement maturity: M1 — stock-detector demo.** Genuine YOLO inference runs, but counts, speed, density, and incident metrics are uncalibrated and unevaluated; several are physically impossible.
- **ML forecast:** real and reproducible, but trained on a synthetic benchmark and only +0.22pp over a lookup baseline; no baselines published.
- **UI:** feature-rich but broken at laptop widths, contains fabricated/overclaimed values, an auth bypass, and dead Live-CCTV code.
- **Evaluation:** prediction accuracy exists; vehicle-detection accuracy and dashboard responsiveness (explicit requirements) are missing.

---

## 2. Official requirement scorecard

| # | Requirement | Status | Summary |
|---|---|---|---|
| 1 | Intelligent traffic monitoring dashboard | **Partial** | Six overlapping tabs; header breaks at 1280–1440; `/live_traffic` 404; heat overlay missing; hardcoded KPIs |
| 2 | Detect vehicle density using CV | **Demo-grade** | 2D bbox/ROI occupancy only; no physical density; ROI polygon ignored; stock COCO, no auto-rickshaw class; ≈38–45% recall |
| 3 | Predict congestion with ML | **Partial** | 86.98% reproducible, but synthetic data; +0.22pp over lookup; live features fabricated; horizon mislabeled 15m |
| 4 | Recommend optimized signal timings | **Partial** | Webster exists; inputs hardcoded/derived; same 150s for Severe corridors; no validation |
| 5 | Generate alternate route recommendations | **Partial** | Dijkstra/BPR works; constant 8.5km, fabricated alternate volume/time, 2–3 corridor points, not a road path |
| 6 | Evaluate prediction accuracy and system performance | **Fails** | No detection accuracy, density/speed/incident validation, or dashboard responsiveness benchmark |

---

## 3. What is genuinely working

- Genuine YOLO11n inference (MPS/CPU, CPU fallback, no synthetic boxes in normal mode), typed errors, verified H.264 annotated output (~28–38 fps at 720p).
- Chunked 256MB upload, SHA-256, async job queue/persistence, ownership checks, HTTP Range streaming.
- XGBoost artifacts and pure-Python inference; 86.98% holdout accuracy reproduces exactly (86.9781%).
- Webster optimizer, Greenshields simulation, Dijkstra routing, event manager, PBKDF2 auth primitives, Google Maps/Places browser integration, 24-corridor topology.
- 216 collected tests: 212 pass, 3 skip, 1 env-dependent fail on a clean clone; 74% statement coverage; 212 pass in ~42s when the heavy video test is excluded.
- The engineering around the model/detector is more mature than the science inside it.

---

## 4. CV findings

Evidence: full report at [`evidence/CV_AUDIT_REPORT.md`](evidence/CV_AUDIT_REPORT.md); measured pipeline outputs in `/tmp/cv_audit/out/`.

### 4.1 Detector
- Only weight file is stock `yolo11n.pt` (COCO-80); no fine-tuning config, labels, data.yaml, training logs, or ONNX.
- `COCO_VEHICLE_MAP` = bicycle/car/motorcycle/bus/truck (`traffic_system/computer_vision/detector.py:22-35`); no auto-rickshaw, LCV, or Indian-traffic class.
- Manual frame audit: 73 visible vehicles across 14 sampled frames → 28 detected (~38% recall, ~50% class-correct). Indian street group 21/47 (~45%); Seville group 7/26 (~27%).
- Every observed auto-rickshaw was missed or mislabelled `truck`/`motorcycle`/`pedestrian`; one truck box enclosed 2–3 rickshaws; distant motorway cars often produced 0 detections at imgsz 640.
- Raising imgsz 640→1280 recovers some distant detections, so resolution loss is part of the problem.
- No mAP/precision/recall/ground truth exists anywhere in the repo or git history. CV tests assert invariants, never accuracy.

### 4.2 Measured end-to-end outputs

| Clip | Real content | Frames | "Unique vehicles" | Class split | PCU/hr | Speed | Density peak | Incidents |
|---|---|---:|---:|---|---:|---|---|---:|
| `sample_outer_ring.mp4` 5s | Indian street, autos/cyclists (actually first 5s of North-East.mp4) | 150 | 9 | 0 car, 6 moto, 2 bicycle, 1 truck | 4,608 | 8.9 proxy | 16.0% Moderate | 15 decel (10 ped, 5 bicycle) |
| `sample_traffic.mp4` 9s | Seville, Spain bus stop / motorway | 270 | 16 | 15 car, 1 bus | 7,112 | 20.4 proxy | 92.8% Severe | 49 decel (44 car, 5 bus) |
| `North-East.mp4` first 30s | Indian street, Bengali signage | 900 | 65 | 11 car, 17 moto, 13 bicycle, 2 bus, 22 truck | 11,244 | 16.8 proxy | 81.1% Severe | 303 (300 decel, 3 wrong-way) |
| `North-East.mp4` 120s committed artifact | same | 3,600 | **274** | 29 car, 100 moto, 36 bicycle, 5 bus, 104 truck | 12,366 | 14.7 proxy | 100% | **962** (955 decel, 7 wrong-way) |

- 274 vehicles in 120s on a single-lane street = 8,220 veh/h; 628 tracks created; direction totals 162 vs 274.
- 870/955 decelerations are <−8 m/s² (human/vehicle limit); minimum −350.8 m/s². 589/962 incidents are pedestrians.
- The UI displays "0 active incidents" because backend `incident_summary.incidents` is read as `recent_incidents` (`app/static/app.js`).

### 4.3 Measurement defects
- **Speed:** hardcoded generic homography, `is_calibrated=False` (`speed_estimator.py:19-23,43-44`); DLT calibration is dead code unreachable from HTTP (`vision_routes.py:331-336`); proxy speeds >100 km/h in a bus-stop clip; `calibrated_speed_kmh` label in `live/bridge.py:773` is false.
- **Density:** 2D bbox-area/ROI occupancy; `roi_polygon` documented but never used; UI computes "Greenshields Density" = PCU/h ÷ proxy speed → 518 veh/km (jam density ≈120–150) (`app.js:5682-5686`).
- **Incidents:** no active-lane geometry, no vehicle-only gate, default 90° wrong-way bearing, no decel clamp/dedup; 59% pedestrians, 87% impossible magnitudes; no ground truth.
- **Tracking/counting:** custom IoU (not ByteTrack); newborn tracks marked LOST immediately (`tracker.py:243-249`); `min_hits=1`; 60px/frame vehicle → 10 IDs; occlusion duplicates; new vehicle absorbed into old ID; fake `id_switches_prevented`.
- **PCU:** 5–9s clips extrapolated to hourly rates; one extra truck = +2,160 PCU/h; auto factor unreachable; pedestrians priced at 1.0 PCU on live path.
- **CV→ML:** injector ignores measured counts/PCU/mix/incidents; volume = static 32,000 baseline × occupancy (`traffic_physics.py:85-93`); `capacity_utilization` passes lane count as capacity → always 100.0; live-frame path uses 30%/28 km/h defaults; current clock not capture time; provenance "Live Optical CCTV AI" on uploaded non-Bengaluru clips. A real congested CV state produced **Low 45.5%**.
- **Camera input:** upload only; no RTSP/webcam/CCTV; samples are Seville, Spain and North-East India (not Bengaluru); `sample_outer_ring.mp4` is the first 5s of `Dataset/North-East.mp4`.

---

## 5. ML/data findings

Evidence: `/tmp/audit/` scripts and JSON (ML audit).

- Raw dataset: 57,600 rows × 16 cols, 24 roads, 8 zones, 100 dates (2022-01-01..2022-04-10), exactly 24 rows per road-date, no nulls/dups. Loader yields 57,576 after dropping 24 boundary rows.
- **Synthetic proof:** `Congestion Level = 45.0159·TTI − 45.0286`, R² = 0.999976, max residual 0.223 on all 57,600 rows; perfect full-factorial grid; 57,572/57,576 unique 7-feature vectors. README's "real Kaggle observations" is false.
- Hour is derived by within-(date,road) cumcount; plausible diurnal curve (peak hour 17, weekday hour 9), but unprovable from the file.
- Labels: `<50/<75/<90` → Low 27,852 (48.37%), Moderate 16,747, High 7,109, Severe 5,868.
- Model: 80 rounds × 4 classes = 320 trees, depth 4, lr 0.05, multi:softprob; pure-Python inference matches XGBoost argmax on 99.98% of rows (not bit-exact probabilities; mean Δ 2.7e-4).
- Chronological holdout 86.98% reproduces exactly, but:
  - majority 48.23%;
  - persistence 70.68%;
  - `(road, hour, current LOS)` mode lookup **86.76%**;
  - model 86.98% → +0.22pp over lookup.
- No baseline published anywhere; no validation/tuning/early stopping.
- Silent fabrication in predictor: `{}` → Moderate 0.66; missing hour → 17; malformed LOS → Low; NaN and 1e9 volume give identical output; hour 99/−5 accepted; cap_util 9999 unclamped.
- `Dataset/traffic_prediction_results.csv` and `congestion_comparison.csv` are stale outputs of `scripts/demonstrate_pipeline.py`: label map `<40/<70/<90`, hardcoded per-road peak hour, random stratified split, fabricated boundary targets, different model. Docs publish those numbers as current out-of-time results.
- Live providers:
  - `.env` base URLs point at web-console pages (`my.tomtom.com/keys...`, `console.cloud.google.com/...`), causing 403; status misdiagnoses as network/key failure.
  - Placeholder weather key causes Open-Meteo 400, so weather always falls back to baseline.
  - Live grid at peak hour: 23 Moderate + 1 Low, 0% High/Severe vs history 42.8%.
- `/api/dispatch/directives`: hardcoded volumes 1885/1359/703/177, lanes=2, mixes peak aggregates with wall clock; Webster returns same 150s for every Severe corridor.
- `/api/zones/summary`: "predicted" distribution equals observed distribution (`pred_dist == cong_dist`), not a model output.
- `/api/map/heatmap`: no provenance/is_live field; 72 points, 2 intensities.
- Live route fallback: constant 8.5 km, alt_vol = 0.72×primary, floor time-saved 2.5/3.5 min, 2–3 corridor IDs rather than a road path.

---

## 6. UI/API findings

Evidence: [`evidence/UI_API_AUDIT.md`](evidence/UI_API_AUDIT.md); screenshots under [`evidence/`](evidence/).

### 6.1 Layout and navigation
- Header at 1280/1440: `scrollWidth` 1538, role badge 6 lines/91px, user chip clipped, **Sign Out off-screen**; no media queries above 1080 (`app/static/styles.css:75-85,132-145,163-167`).
- Six tabs overlap in purpose: Standard Operations, Live Traffic, Live Simulation, Vision AI, Synthesizer Hub, Heat Map.
- Active tab URL rewrite `/live_traffic` (`app.js:2365`) is not routed by the server (`server.py:77-90`) → raw 404 on refresh.
- Synthesizer tab contradicts itself ("All Subsystems Verified" vs "DEGRADED" vs "6/6 Optimal") and is out of scope.

### 6.2 Runtime/JS errors
- Every page load: `ReferenceError: startClientInferenceLoop is not defined` (only `stopClientInferenceLoop` is defined; dead Live-CCTV export).
- Google HeatmapLayer removed in Maps v3.65: heat overlay never renders (`app.js:4026`); admin heatmap can be stuck at world zoom via hidden-canvas `fitBounds`.
- Missing DOM ids referenced by JS: `btnHeatmapDensity`, `btnHeatmapStrictLive`, `commuterRoutePlannerCard`, `originRoadSelect`, `destinationRoadSelect`, `zoneSelect`, `viewMapHeatmap`, `tabConsoleLabel`.
- 71/481 CSS classes unused; several dead JS functions (`switchMainTab`, `switchPersona`, `selectPersonaView`, etc.).

### 6.3 Auth/security
- Direct `/portal` auto-creates `{role:"Traffic Authority", token:"demo_default_session"}` (`app.js:375-407`); Vision upload then 401s while admin tabs unlock.
- `ENFORCE_ADMIN_AUTH=false` in development allows missing/invalid tokens on admin endpoints (`server.py:239-256`); proven by anonymous `POST /api/events/add` creating a published `OFFICIAL_VERIFIED` event; a valid commuter token gets 403.
- `/api/map/config` exposes the raw Google key unauthenticated.
- README documents `admin/SecurePass@123`, which returns 401; working creds are `admin/Admin@123` / `commuter/Admin@123`.

### 6.4 Fake/overclaimed values
- "ByteTrack" (README/docs) vs custom IoU tracker (`tracker.py:6`).
- "YOLO11n CoreML/MPS" vs actual MPS/CPU; CoreML not used.
- "XGBoost 15m" vs model `prediction_horizon: 1_hour_ahead`.
- "Greenshields Density" client-side PCU/h ÷ proxy km/h.
- "Closed-Loop Grid Actuation" ignores measured counts/PCU/incidents and uses static baseline/occupancy; provenance "Live Optical CCTV AI".
- Hardcoded KPI placeholders: "Estimated Time Saved 15.6 Min" (`index.html:156`), authority KPIs 57,600/26.8%/21 (`app.js:759-761`) vs API 57,576/50%/12.
- Sample clips mislabeled: Seville bus stop and North-East India street; "Outer Ring Road Bellandur" is the first 5s of North-East.mp4.

---

## 7. Tests, repo, deployment

- 216 collected: **212 passed, 3 skipped, 1 failed** on a clean clone; failure is `test_north_east_chunked_upload_and_inference` (requires gitignored 55MB video; `@pytest.mark.integration` not wired to skip). With video, that test takes **161s**; real-repo suite ≈203s vs README's 20.61s.
- 74% statement coverage total; `app/server.py` only **42%**; no coverage gate/CI.
- Tests write repo state: the new `tests/conftest.py` session teardown truncates tracked `vision_jobs.json` and wipes storage; 25/47 commits touch artifacts.
- 13/216 tests only assert file existence/substrings; 20 use mocks; 11 Playwright scripts are not collected by pytest and run manually.
- Docs contradictions:
  - test counts 180/183/212 vs 216;
  - 94 corridors/6 zones/203,906 records/2026 dates vs 24/8/57,600/2022;
  - ByteTrack, TreeSHAP, FastAPI, Random Forest/LightGBM, SQLite, SSE, OpenWeatherMap all absent;
  - "8-feature" vs 7 raw/10 vector dims; wrong zone names; "Apple HIG" is marketing.
- Repo bloat/duplication:
  - `app/static` ≡ `public` (25MB);
  - 3 architecture copies;
  - 47.6MB tracked sample videos;
  - 18.5MB CSVs including generated outputs;
  - 5.35MB `yolo11n.pt`;
  - 143 `.pyc`, 12 `.DS_Store`, tracked runtime state.
- Dead/test-only abstractions: `traffic_system/live/adapters/base.py`, `traffic_system/models/strategies/base.py` (zero implementations; only a test asserts existence).
- Deployment:
  - Docker excludes `architecture/` while UI links `/architecture/*` → 404;
  - Vercel path imports torch against 60s/1024MB/4.5MB limits;
  - `cryptography` missing from requirements;
  - no CI;
  - cache-bust `?v=2.4` unchanged while JS/CSS edited.
- Concurrency: worktree is dirty from another process; see caveat at top.

---

## 8. Stage assessment

| Dimension | Maturity | Notes |
|---|---|---|
| ML forecast | Working prototype (TRL 4) | Reproducible but synthetic, baseline-beating by 0.22pp; no real live features |
| CV measurement | M1 demo | Genuine inference; no Indian class, calibration, counting integrity, or evaluation |
| Routing/signals | Working prototype | Real algorithms; fabricated inputs/route geometry |
| Dashboard | Beta/broken | Broad feature surface; responsive/layout/auth/dead-code defects |
| Evaluation | Partial | ML accuracy only; required CV/dashboard metrics missing |
| Deployment | Prototype | Local works; Docker/Vercel claims not verified; no CI |
| Overall | **Functional single-node capstone prototype, ~60–70% toward demo/report** | Not production; not CV traffic-understanding yet |

---

## 9. What must be kept vs removed

**Keep:** XGBoost artifacts/pure-Python inference, chronological validation, Webster, Greenshields, Dijkstra, event manager, auth primitives, chunked upload/job queue/streaming, 24-corridor topology, Google Maps browser integration, test suite core.

**Remove/quarantine:** Synthesizer tab and synthetic stress lab from product UI, Live Simulation/synthetic presets from main nav, haptic audio, dead Live-CCTV code, undefined JS, hardcoded KPIs, fake labels, stale results CSVs as current output, duplicate static/architecture copies, tracked runtime state, dead ABC scaffolding.

**Rebuild:** CV measurement (data/model/calibration/counting/incidents/eval), CV→ML mapping, live provider config, UI information architecture, test hermeticity/CI, docs truth.

---

## 10. Evidence index

- [`VISION.md`](VISION.md) — target product/roadmap.
- [`evidence/CV_AUDIT_REPORT.md`](evidence/CV_AUDIT_REPORT.md) — full CV measurements, file:line defects.
- [`evidence/UI_API_AUDIT.md`](evidence/UI_API_AUDIT.md) — tab-by-tab UI/API audit.
- `docs/evidence/*.png` — responsive header, vision false metrics, 404, heatmap, synthesizer, standard dashboard.
- `/tmp/audit/` — ML/data scripts and JSON from the ML audit (ephemeral; copy selected outputs to `docs/evidence/` during Phase 0).
- `/tmp/cv_audit/` — CV scripts and pipeline outputs (ephemeral; copy selected outputs during Phase 0).
- `/tmp/dp01_audit_ui/` — UI screenshots and reports (ephemeral; selected copies in `docs/evidence/`).
- `/tmp/dp01_audit_repo/` — isolated test run and coverage report (ephemeral).

---

## 11. Phase 0 update (post-audit)

After this audit, Phase 0 made the fast suite hermetic: `pytest -m "not integration"` yields 213 passed, 4 deselected; plain `pytest` yields 213 passed, 4 skipped (heavy video is opt-in with `RUN_HEAVY_VIDEO_TEST=1`). The original snapshot numbers below are retained as historical evidence.

## 12. Immediate next step

Execute Phase 0 of the approved plan: freeze the worktree, publish this report and VISION, rewrite the README/structure/dataset docs to match reality, remove out-of-scope UI and false claims, fix responsive/auth/route/heatmap/incident bugs, and make the test suite hermetic. Then start Phase 1 (CV dataset/annotation/fine-tune/eval).

The project is salvageable because the ML, routing, and serving engineering is real. The recovery is not another UI polish pass; it is a **measurement-first rebuild of the CV layer** followed by honest integration.

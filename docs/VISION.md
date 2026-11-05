# Vision: Camera-First Traffic Understanding for Indian Cities

**Status:** Approved product direction for the capstone project
**Date:** 2026-11-04
**Project:** AI-Based Smart Traffic Monitoring and Congestion Prediction System (Dp-01)
**Source of truth for requirements:** [`docs/requirements/378_Design Project Problem Statement_6_Rashmi Mothkur.docx`](requirements/378_Design%20Project%20Problem%20Statement_6_Rashmi%20Mothkur.docx)
**Current-state evidence:** [`docs/AUDIT_REPORT.md`](AUDIT_REPORT.md)

---

## 1. Mission

Build a traffic-understanding system that **measures what the camera can see**, **forecasts what happens next hour**, and **recommends what an operator or commuter should do**, without confusing simulated, historical, or proxy values for measured ones.

The system must be able to answer three questions with evidence:

1. **What is the traffic state right now?** — vehicle counts by class, flow, occupancy/density, speed, and safety incidents, derived from a camera or a recorded clip.
2. **What will it be next hour?** — a calibrated congestion forecast, with a published baseline and an explicit statement of the data it was trained on.
3. **What should we do?** — advisory signal timings and alternate routes, computed from the measured state, not from hardcoded constants.

The project succeeds only if vehicle detection accuracy and system performance are measured and reported. A polished dashboard without validated measurements is a demo, not the deliverable.

---

## 2. Problem context

The official problem statement asks for an AI traffic platform that collects data from traffic cameras, GPS services, and public traffic APIs; uses computer vision to detect and count vehicles; uses machine learning to predict congestion; and provides live visualization, congestion heat maps, accident alerts, and route optimization. It explicitly requires evaluating:

- congestion prediction accuracy,
- vehicle detection accuracy,
- dashboard/system performance.

The current implementation has real ML, routing, signal, and serving engineering, but its CV measurement layer is stock-detector demo-grade and its UI/API contains fabricated or mislabelled values. This vision resets the project around evidence.

---

## 3. Users and use cases

### 3.1 Traffic control-room operator
- Monitor several camera feeds and the live corridor map.
- See measured flow, occupancy, mean speed, and validated incidents.
- Inspect the next-hour forecast and its drivers/uncertainty.
- Receive advisory Webster signal timings and alternate-route options.
- See provenance and calibration state for every number.

### 3.2 Commuter / road user
- Choose origin, destination, date, and departure time.
- See predicted congestion for the direct route.
- Get an alternate route with an evidence-based time estimate.
- Understand whether the data is live, cached, historical, or simulated.

### 3.3 Evaluator / faculty reviewer
- Open an evaluation page and see detection mAP, per-class precision/recall, counting error, speed/density validation, incident precision/recall, prediction accuracy plus baselines, and dashboard latency.
- Reproduce the results from committed scripts and data.

---

## 4. Product principles

1. **Measurement first.** The CV layer is the source of traffic state. The ML layer forecasts from measured state. The decision layer acts on forecasts. Do not invert this order.
2. **Evidence or silence.** Every displayed metric must have a source, timestamp, model version, calibration state, sample size, and provenance label. If it is not measured, show "not measured", not a plausible number.
3. **Calibration gates physical units.** Speed in km/h and density in veh/km require per-camera calibration. Without calibration, report "proxy speed" or "occupancy %" and exclude the value from prediction, signals, and routes.
4. **Evaluate the required things.** Detection accuracy and dashboard responsiveness are first-class deliverables, not optional extras.
5. **No invented data.** No synthetic detections, no fabricated volumes, no hardcoded dispatch numbers, no fallback presented as live.
6. **Scope discipline.** The product surface is monitoring, CV measurement, forecasting, signal advisories, route advisories, and evaluation. Internal dev tooling (synthetic stress lab, API-key studio, storage snapshots) does not belong in the main dashboard.
7. **Advisory only.** Signal recommendations are decision support. The system does not actuate physical controllers.
8. **One source of truth.** `docs/VISION.md` defines the product; `docs/AUDIT_REPORT.md` records the current baseline; `docs/EVALUATION.md` records measured results. README and UI must agree with these or be wrong.

---

## 5. Target architecture and data flow

```
Camera file / RTSP / recorded clip
        │
        ▼
Camera Registry
  camera_id, corridor_id, location, capture_time
  ROI polygon, lane polygons, 4-point homography, speed limit
        │
        ▼
Detector (fine-tuned Indian-traffic model)
  car, motorcycle, auto-rickshaw, bus, LCV/truck, bicycle, pedestrian
        │
        ▼
Tracker + counter
  ByteTrack/BoT-SORT, confirmed tracks, line crossings, parked filter
        │
        ▼
TrafficMeasurement
  counts, flow (vph / pcu_per_h), occupancy %, density (calibrated or heuristic),
  speed (calibrated or proxy), incidents, calibration/model/provenance metadata
        │
        ▼
Traffic State Store
  per corridor + capture time + quality flags
        │
        ├──────────────► Forecast (XGBoost, next-hour)
        │                  measured features; baselines; reject missing/OOD
        │
        └──────────────► Decisions
                           Webster signal timings, alternate routes, event impact
        │
        ▼
Dashboard
  Monitor (camera + measured state + incidents + map)
  Predict (forecast + map/heat overlay + model evidence)
  Decide  (signal timings + routes + events)
  Evaluation (CV/ML/system metrics)
```

Historical benchmark data (57,600 records, 24 corridors, 8 zones, 2022) and TomTom/Open-Meteo are **context and fallback only**. They are not live measurements and must be labelled.

---

## 6. Measurement contract

### 6.1 Vehicle classes
Train and evaluate on the classes the deployment actually sees:

| Class | PCU factor (Indo-HCM guidance) | Notes |
|---|---:|---|
| car | 1.00 | includes taxi/van if indistinguishable |
| motorcycle / two-wheeler | 0.50 | dominant Indian class |
| auto-rickshaw / three-wheeler | 0.80 | mandatory for Indian streets; stock COCO cannot detect it |
| bus | 2.80 | transit bus |
| LCV / truck | 3.00 | separate LCV if data supports it |
| bicycle | 0.20 | |
| pedestrian | excluded from vehicle flow | count separately for safety |

The detector must not silently map an auto-rickshaw to `truck` or a pedestrian to a vehicle. Unknown objects are `unknown`, not counted.

### 6.2 Time and flow
- A measurement covers a declared window `[capture_start, capture_end]` with `interval_s`.
- Flow is `count / interval_s × 3600` vph only for windows of **at least 5 minutes**; shorter clips are reported as a sample estimate with a confidence interval or as raw counts, not as hourly flow.
- The forecast horizon is **next hour (1h)**. It is never labelled "15m" unless a real 15-minute model exists.
- The forecast uses the capture time of the measurement, not the wall clock at request time.

### 6.3 Calibration
- A camera is calibrated when it has a verified 4-point planar homography (or equivalent) with a reported reprojection error.
- Calibrated speed is validated against GPS/radar on at least two clips; report MAE.
- Density is reported as `veh/km/lane` only when calibrated ground area is known. Otherwise report `occupancy_pct` with the bbox/ROI method.
- Uncalibrated values are tagged `proxy` in the API and UI and cannot be used by prediction, Webster, or route decisions.

### 6.4 Incidents
- Evaluate vehicle classes only.
- Require an active-lane polygon (not the whole frame).
- Stall: dwell beyond threshold in the lane; parked vehicles excluded.
- Wrong-way: relative to calibrated lane bearing.
- Hard braking: clamp physically plausible deceleration (≤10 m/s²); deduplicate per track.
- Until precision/recall are measured on labelled clips, label these "hard-braking/stop advisories", not "accident alerts".

### 6.5 Provenance
Every measurement and response carries:
- `source`: camera/clip/API/historical;
- `is_live`, `is_cached`, `is_simulated`;
- `calibration`: `is_calibrated`, `method`, `reprojection_error_px`;
- `model`: name, version, classes, input size, confidence threshold, device;
- `quality_flags`: low light, occlusion, short sample, uncalibrated, out-of-distribution.

---

## 7. Requirements traceability

| Official objective | Product capability | Evidence required |
|---|---|---|
| 1. Intelligent traffic monitoring dashboard | Monitor view: camera/clip, measured state, map, incidents, provenance | E2E test + screenshots at 1280/1440/1920; no console errors |
| 2. Detect vehicle density using CV | Measurement contract: fine-tuned detector + tracker + calibration/density | mAP, per-class P/R, count MAE, occupancy/density error |
| 3. Predict congestion with ML | Next-hour forecast from measured state; baselines; calibration | Chronological holdout accuracy, macro-F1, baseline table, ECE |
| 4. Recommend optimized signal timings | Webster advisory from measured approach flows | Formula test + evidence values traceable to inputs; advisory disclaimer |
| 5. Generate alternate route recommendations | Route engine using measured state/events | Route E2E; no fabricated distance/time; provenance |
| 6. Evaluate prediction accuracy and system performance | Evaluation page + committed report | CV metrics + ML metrics + latency/throughput |

---

## 8. Current baseline (2026-11-04)

- Integrated single-node prototype; real ML/CV/physics/routing. Phase 0 fast suite: 217 collected, 213 pass, 4 opt-in/skip (heavy video and live-API tests excluded).
- CV maturity M1: stock COCO YOLO11n, no fine-tuning, no auto-rickshaw class, no mAP/annotations, uncalibrated speed, occupancy heuristic, incident noise.
- ML: reproducible 86.98% on a synthetic 57,600-row benchmark; only +0.22pp over a `(road, hour, current LOS)` lookup; no baseline published; CV→ML mapping uses fabricated defaults and a label-space mismatch.
- UI: six overlapping tabs, header broken at laptop widths, fake labels/hardcoded KPIs, dead Live-CCTV code, no heat overlay, demo-session auth bypass.
- Data: `traffic_prediction_results.csv` and `congestion_comparison.csv` are stale outputs of a different pipeline; docs treat them as current.
- Deployment: Docker/Vercel claims not verified; `/architecture` links 404 in Docker; no CI; missing dependency.
- Stage: functional capstone prototype, ~60–70% toward a solid demo/report; not production; not yet a CV traffic-understanding system.

---

## 9. Roadmap and exit criteria

### M0 — Truth reset (Phase 0, 1–2 days) — **implemented 2026-11-04**
Remove false claims, fluff tabs, fake KPI values, demo auth bypass, dead Live-CCTV code; fix responsive shell, route 404, heat overlay, incident key; make tests hermetic; add VISION/AUDIT/requirements; freeze working tree.
**Exit:** fast suite 217 collected / 213 pass / 4 skipped; no console errors; no horizontal scroll at 1280–1920; anonymous admin writes return 401; docs match code. See Phase 0 verification in `README.md` and screenshots in `docs/evidence/`.

### M1 — Honest CV measurement layer (Phase 1, 2–3 weeks)
Collect/licence Indian traffic clips; annotate 1,500–3,000 frames; fine-tune YOLO11s/m; implement ByteTrack/BoT-SORT counting; per-camera calibration; ROI polygons; incident plausibility; evaluation harness.
**Exit:** detection mAP50 ≥0.60, mAP50-95 ≥0.35, auto-rickshaw AP50 ≥0.50, count MAE ≤15%, IDF1 ≥0.60; calibrated speed MAE ≤8 km/h; occupancy MAE ≤5pp; incident precision ≥0.70/recall ≥0.60; report committed. If data cannot support, mark objective 2 partial and publish the gap.

### M2 — Measured state → forecast (Phase 2, 3–5 days)
TrafficMeasurement schema/state store; strict CV→ML mapping (measured flow/PCU, real capacity, training-threshold LOS, capture time); remove defaults/hardcoded dispatch values; fix provider config; publish baselines and synthetic-data caveat.
**Exit:** one end-to-end test from clip → measurement → forecast → signal/route response with every value traceable; real congested clip no longer predicts "Low"; baselines in report/UI.

### M3 — Dashboard alignment and evaluation (Phase 3, 3–5 days)
Monitor/Predict/Decide/Trip views; evaluation page; responsive design; heat overlay; provenance badges; performance benchmark; Playwright E2E.
**Exit:** no console errors, no 404, no horizontal scroll; page load <2s local, API p95 <300ms local; E2E green; all six objectives visible or explicitly marked partial.

### M4 — Hardening, deployment, documentation (Phase 4, ~1 week)
Clean repo/duplicates/runtime state; CI; Docker/Render verification; Vercel scope (static/demo only); dependency/security fixes; final docs and evaluation report.
**Exit:** clean clone installs/runs; Docker health verified; deployment links valid; docs/test counts accurate; `docs/EVALUATION.md` complete.

### M5 — Real-data pilot (optional, beyond capstone)
Live camera feed(s), real municipal/API data, calibration survey, operational advisory trial. Only if data access and permissions exist.

---

## 10. Evaluation protocol

### 10.1 Detection and counting
- Dataset: video-level split (no frames from the same clip in train and test).
- Labels: bounding boxes for 6 vehicle classes + pedestrian; count lines/ROI ground truth.
- Metrics: mAP50, mAP50-95, per-class precision/recall/F1, count MAE/ME, IDF1/MOTA.
- Report the stock-model baseline and the fine-tuned model; no cherry-picked frames.

### 10.2 Speed, density, incidents
- Speed: calibrated MAE vs GPS/radar; otherwise no physical claim.
- Density/occupancy: MAE vs manual ROI counts/occupancy; report the method.
- Incidents: precision/recall on labelled clips; confusion by incident type; false alarms per hour.

### 10.3 Prediction
- Chronological date split (80/20), no random shuffle across dates.
- Baselines: majority, persistence, `(road, hour, current LOS)` mode lookup.
- Metrics: accuracy, macro-F1, weighted-F1, per-class P/R, confusion matrix, ECE/confidence calibration.
- Clearly state the dataset is synthetic if it is; do not call it real Kaggle observations.

### 10.4 System
- Dashboard first contentful paint / load time at 1280×720 and 1920×1080.
- API latency p50/p95 for roads, forecast, route, CV job status.
- CV processing throughput (fps) and job completion time for a fixed clip.
- Reproducible commands and committed results.

---

## 11. Data governance and truth policy

- **Required labels:** `LIVE`, `CACHED`, `HISTORICAL`, `SIMULATED`, `PROXY`, `UNCALIBRATED`.
- **Forbidden:** synthetic detections in normal mode; hardcoded volumes/predictions; fallback labelled as live; "Bengaluru" labels on non-Bengaluru clips; metrics without a source.
- **Dataset provenance:** record source URL/licence/date for every dataset and clip. The 57,600-row benchmark is a synthetic hourly benchmark unless proven otherwise; say so.
- **Stale artifacts:** do not publish `traffic_prediction_results.csv`/`congestion_comparison.csv` as current model output. Regenerate from the shipping model and current label mapping, or move to `docs/evidence/stale/` with a warning.
- **Secrets:** never commit API keys, session tokens, or raw user data; demo credentials must be documented and env-driven.

---

## 12. Non-goals

- Autonomous physical traffic-signal actuation (SCATS/CoSiSYS integration).
- Statewide/multi-city scale, Kafka/ST-GNN/MARL/Kubernetes for the capstone.
- A synthetic "stress lab" or API-key studio in the user-facing dashboard.
- Claiming "production-grade" without CI, monitoring, and real data.
- Rewriting working ML/routing code solely for novelty.

---

## 13. Risks and dependencies

| Risk | Impact | Mitigation |
|---|---|---|
| No licensed Bengaluru camera footage | CV eval blocked | User-provided clips or public Indian dataset + explicit domain-gap note |
| Annotation time | Long pole | Start with 1,500 frames, 6 classes; active learning; video-level split |
| Compute for fine-tuning | Delay | YOLO11s/m at 960–1280 on MPS/GPU; checkpoint and report |
| Synthetic ML dataset | Credibility | Publish baselines and caveat; add real data if available |
| API keys/base URLs | Live data broken | Correct config, startup probe, fallback tags, no fabricated features |
| Vercel limits | CV cannot run | Render/local for CV; Vercel static/demo only |
| Concurrent agents editing | Merge conflicts | Freeze worktree; one writer per scope; Lead reviews diff |
| Scope/time | Incomplete | Phase gates; do not claim unmet objectives |

---

## 14. Definition of done

The project is done for the capstone when:

1. The official six objectives each have a measured, linked evidence entry in `docs/EVALUATION.md` (or an explicit partial status with reason).
2. The UI shows only values with provenance and never a fabricated metric.
3. The CV detector has a published mAP/per-class report on a held-out Indian-traffic set, and the counting/speed/density/incident validity rules are enforced.
4. The forecast is reported against published baselines with its dataset provenance and calibration.
5. Signal and route recommendations are computed from measured state and labelled advisory.
6. Dashboard responsiveness is measured and reported.
7. A clean clone installs, runs, and passes its documented test suite; CI is green; deployment is verified.
8. README, VISION, AUDIT, EVALUATION, and UI agree.

---

## 15. Source-of-truth hierarchy

1. Official problem statement (`docs/requirements/...docx`).
2. This vision.
3. `docs/EVALUATION.md` for measured results.
4. `docs/AUDIT_REPORT.md` for the current baseline and defects.
5. README/UI (must be consistent with 1–4; otherwise they are wrong).

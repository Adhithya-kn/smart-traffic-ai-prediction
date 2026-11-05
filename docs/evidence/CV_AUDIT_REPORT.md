# CV Audit — AI-Based Smart Traffic Monitoring (Dp-01)
Read-only audit. Repo not modified. Evidence in `/tmp/cv_audit/` (scripts + raw JSON). All numbers re-measured on this machine with the repo's own code, `yolo11n.pt` (stock COCO-80), MPS, conf 0.30, imgsz 640, 2026-11-04.

## VERDICT: maturity M1 — "stock-detector demo" (0 of 4 CV measurement claims calibrated or evaluated)
Genuine YOLO11n inference runs and is wired to a polished dashboard, but every *traffic measurement* built on it (count, speed, density, incident) is uncalibrated, unevaluated and in several cases mathematically impossible. No fine-tuning, no Indian classes, no annotated data, no mAP/precision/recall, no calibration path, no live CCTV ingestion.

## 1. End-to-end measurements (repo pipeline, output in /tmp)
| clip | real content | frames | unique ("vehicles") | class split | PCU/hr (extrap.) | speed | density avg/peak | incidents |
|---|---|---|---|---|---|---|---|---|
| `app/static/sample_outer_ring.mp4` (5.0 s, 1280x720) | Indian street, auto-rickshaws + cyclists | 150 | 9 | car0, moto6, bicycle2, bus0, truck1 | 4,608 | 8.9 km/h `UNCALIBRATED_PROXY` | 10.2 % / 16.0 % Moderate | 15 decel (10 pedestrian, 5 bicycle), 0 stalled, 0 wrong-way |
| `app/static/sample_traffic.mp4` (9.0 s, 960x540) | Seville, Spain bus stop, then Spanish motorway | 270 | 16 | car15, bus1 | 7,112 | 20.4 km/h proxy | 32.0 % / 92.8 % Severe | 49 decel (44 car, 5 bus), 0 stalled |
| `Dataset/North-East.mp4` first 30 s | Indian street (Bengali signage, SARKAR bus) | 900 | 65 | car11, moto17, bicycle13, bus2, truck22 | 11,244 | 16.8 km/h proxy | 16.5 % / 81.1 % Severe | 303 (300 decel, 3 wrong-way) |
| same video 120 s — **committed artifact** `git show HEAD:traffic_system/artifacts/vision_jobs.json` job `cv_baad82587f` | same | 3600 | **274** | car29, moto100, bicycle36, bus5, truck104 | 12,366 | 14.7 proxy | peak 100 % | **962**: 955 decel (589 pedestrian, 186 truck, 63 moto, 58 bus, 43 bicycle, 23 car), 7 wrong-way, 0 stalled |

Sanity: 274 unique in 120 s = **8,220 veh/h** on a single-lane residential street; 9 unique in 5 s = 6,480 veh/h; 65 in 30 s = 7,800 veh/h. Tracker created 628 tracks for 274 counted in 120 s (32 tracks → 9 counted in 5 s). Direction counters sum 162 vs 274 counted (120 s), 37 vs 65 (30 s), 5 vs 9 (5 s).
Incident physics: 870/955 decel events in 120 s are < −8 m/s² (human/vehicle braking limit), minimum −350.8 m/s²; in 9 s clip 46/49 < −8, min −265.6. **589/962 "incidents" are pedestrians.**

## 2. Detector quality vs manual frame counts (basis: 14 sampled frames; I visually counted all vehicle-class objects ≥ ~25 px incl. parked, excluding pedestrians; compared with raw YOLO11n conf 0.25)
| group | visible vehicles (manual) | detected | approx recall | class notes |
|---|---|---|---|---|
| `sample_outer_ring` / `North-East` street, 8 frames | 25 + 22 = 47 | 10 + 11 = 21 | **≈ 45 %** | **every** auto-rickshaw missed or labelled `truck`/`motorcycle`; parked autos frequently missed; 0 correct `auto` labels (class does not exist) |
| Seville clip, 4 frames (bus stop + motorway) | 26 | 7 | ≈ 27 % | near bus/cars correct; distant motorway cars 0–4 detected per frame |
| all 14 frames | 73 | 28 (~50 % class-correct) | **≈ 38 %** | object-level precision high (no obvious phantom vehicle boxes); class precision poor on Indian traffic |

Concrete frame evidence: auto-rickshaw → `truck 0.40/0.46/0.79` (outerring_00000/00037, northeast_02553); one truck box encloses 2–3 rickshaws; outerring_00141 near rickshaw yields only `person`, no vehicle box; northeast_02553 four visible vehicles → 2 `truck` + 1 `bicycle`; motorway frame sevilla_00255 ~8–9 visible cars → **0 detections**. Raising `imgsz` 640→1280 recovers some: sevilla_00255 0→4 cars, northeast_02553 3→4, outerring_00111 1→2 — i.e. recall loss is partly a resolution (not just class) failure.

`COCO_VEHICLE_MAP` = {1 bicycle, 2 car, 3 motorcycle, 5 bus, 7 truck} (`detector.py:22-35`) — no auto-rickshaw/LCV/Indian class. `yolo11n.pt` at repo root is stock COCO (5.6 MB), the only weight file; no training config, no `data.yaml`, no labels, no runs.

## 3. Correctness experiments (scripts in /tmp; all reproduced)
**Tracker/counter (`tracker.py`, `vehicle_counter.py`)** — 10 defects confirmed:
1. Stage 4 marks every *just-created* track `LOST` in its birth frame (`tracker.py:243-249`): after frame 1 a new track is `LOST`, `is_confirmed=False`; its 2nd hit can only match via the LOST/recovery path. Verified in unit run.
2. One vehicle moving 60 px/frame → **10 new track IDs**; counter with `min_hits=1` (`vehicle_counter.py:23,96-106`; pipeline instantiates `VehicleCounter()` at `video_processor.py:126`) counts **10 unique vehicles**.
3. 15-frame occlusion → return at predicted position gets **new ID**; counter = 2 for 1 real vehicle (recovery only projects `min(lost_frames,5)` frames, `tracker.py:99`).
4. Vehicle A leaves, different vehicle B appears 5 frames later at the same spot → absorbed into A's ID; counter = 1 for 2 real vehicles (`tracker.py:196-225`).
5. Cross-category association at IoU ≥ 0.35 means class label can be re-voted on a wrong track; `class_id` frozen to first label (`tracker.py:169-177,65-72`).
6. `id_switches_prevented` is fictitious: it increments when a *pedestrian* detection overlaps an active vehicle track at IoU ≥ 0.55 (fall-through `tracker.py:178-179`); pipeline reported 19 (5 s), 65 (30 s), 335 (120 s).
7. `min_hits` default is 1, so a single-frame spurious detection permanently enters the unique count (tests use min_hits=2, pipeline does not).
8. Direction counters only increment on a *change after* counting; single-frame tracks never get a direction → totals don't reconcile (5 vs 9; 162 vs 274).
9. `T4`/`T3` defects mean duplicates under-count and ID churn over-count simultaneously; net count is not auditable.
10. New-track speed history is keyed to a reused `_next_id` reset only on `reset()`; fine per job, but no re-identification beyond IoU.

**Speed (`speed_estimator.py`)** — uncalibrated proxy presented as physical:
- Default `is_calibrated=False`; `GENERIC_HOMOGRAPHY_REFERENCE` hardcoded (`speed_estimator.py:19-23,43-44`) → arbitrary m/px (~0.019 m/px, i.e. 1280 px ≈ 24 m of ground) with no relation to the scene. Same 10 px/frame motion reads 20.1–22.9 km/h depending on frame row.
- Bbox height jitter on a stationary vehicle yields 16.5 km/h spikes; real pipeline produced proxy speeds >100 km/h in the Seville bus-stop clip and −265 m/s² "decelerations".
- `from_four_point_correspondence` DLT is numerically correct (synthetic test: truth 18.0 km/h → estimate 17.9), **but it is dead code for HTTP jobs**: `handle_process` never parses/passes `camera_config` (`vision_routes.py:331-336`), `submit_job(camera_config=...)` exists but only internal callers no-op it, `job_manager.py:185` passes whatever it gets. No calibration API/UI exists (grep of `app/` finds only explanatory text). Every production speed is the uncalibrated proxy.
- Keyword "calibrated_speed_kmh" is exposed to the UI/actuation chain (`bridge.py:773`) and "Space-Mean Speed" / "physical speed calibrated via planar homography" copy is shown (`index.html`, `app.js:5688-5690`).

**Incident detector (`incident_detector.py`)**:
- Stalled rule: any detection at ≤2 km/h for 12 s = "stalled in active lane" High severity; no lane geometry, no parked-vs-stalled discriminator. Verified unit: roadside parked object → incident.
- Wrong-way: default bearing 90° (`incident_detector.py:38`); a vehicle travelling up-frame on a normal outbound two-way lane is flagged after 8 frames (verified; 180° deviation). 7 wrong-way events in 120 s include pedestrians.
- Deceleration: only gate is `prev_speed > 20 km/h`; 60→0 km/h in one frame → **−500 m/s²** accepted (verified unit). No |a| clamp, no hysteresis, no dedup: one incident *per frame* while decaying. Real outcome: 955 decel incidents/120 s, 59 % on pedestrians, 87 % physically impossible; UI never shows them because of a key mismatch (below).
- Zero incidents have ground-truth labels; there is no accident/incident evaluation set at all.

**Density (`density_estimator.py`)**:
- ROI occupancy = Σ clipped bbox area / ROI rect; camera-geometry dependent (same vehicle near vs far: 13.1 % vs 0.6 %). Not veh/km/lane.
- `roi_polygon` documented "non-rectangular carriage-way polygon" (`density_estimator.py:28,37`) is **never used** in `estimate()` — verified: centre point outside polygon still counted. Camera ROI "calibration" is silently discarded.
- LOS thresholds are hand-set (≥3 vehicles = Moderate, ≥12 = Severe; ≥55 % area = Severe) with no traffic-engineering basis; a bus at a stop → peak 92.8 % / 100 % "Severe"; far field (y < 30 % frame) excluded entirely.
- UI compounds it: "Greenshields Density" = `PCU/h ÷ proxy km/h` (`app.js:5682-5686`) → outerring 4608/8.9 = **518 veh/km**, sevilla ≈ 349 veh/km (jam density ≈ 120–150) — physically impossible, shown as `veh/km`.

**PCU (`pcu_converter.py`)**:
- Extrapolation q = PCU/Δt×3600 from 5–9 s clips: 4,608 / 7,112 / 11,244 / 12,366 PCU/h; one extra truck in a 5 s clip = **+2,160 PCU/h**. Metadata does say `is_actual_measured_hourly_flow:false` (good) but the UI headline is "Indo-HCM PCU Flow".
- Auto-rickshaw factor 0.80 is defined but unreachable (no detector class). 10 autos misdetected as truck = 30 PCU vs 8 PCU true (×3.75 overstatement); unknown classes silently default to 1.0 PCU (`pcu_converter.py:56-60`).
- Live-frame endpoint builds `class_counts` incl. pedestrians then feeds `calculate_total_pcu` (`vision_routes.py:565-582`) → pedestrians priced at 1.0 PCU.

## 4. CV → rest-of-system trace
- Stored per job: `results` with class counts, directions, PCU telemetry, kinematics, density, incident_summary, confidence, sample_telemetry(40 rows only) (`video_processor.py:413-470`, `job_manager.py:216-224`). UI renders PCU, speed, occupancy, fake veh/km, confidence (`app.js:5619-5726`).
- Incident UI always shows **0**: backend key is `incidents`, frontend reads `incidents.recent_incidents` (`app.js:5709`) → 962 real (noise) incidents displayed as "Zero active safety incidents". (The bug hides the false-positive problem.)
- "Closed-Loop Grid Actuation": frontend posts whole pipeline result to `/api/vision/live/actuate` (`app.js:5727-5783`). `bridge.inject_vision_telemetry` uses **only** occupancy % and proxy speed (`bridge.py:712-722`); **unique count / PCU / class mix / incidents are ignored**. Volume = static `baseline_volume` default 32000 × (0.55 + 0.95·occ/100) (`traffic_physics.py:85-93`), then XGBoost + Webster (`bridge.py:727-749`). Empty metrics → fabricated defaults occ 30 %, speed 28, volume 26,720 PCU/h, "Moderate" (verified). Result stamped `data_provenance:"Live Optical CCTV AI"` (`bridge.py:763`) for an arbitrary uploaded clip on any of 24 corridors; no camera↔corridor mapping exists.
- No live camera data at all: no RTSP/webcam/CCTV source in repo; only prerecorded MP4 upload; `/api/vision/live/frame` is unwired (`startClientInferenceLoop` referenced at `app.js:5878` but never defined). "Live visualization" = playback of a batch-annotated MP4.
- Sample-video provenance: `app/static/sample_traffic.mp4` is Seville, Spain (city bus "cero emisiones", then a Spanish motorway from frame ~110). `app/static/sample_outer_ring.mp4` is **the first 5 s of `Dataset/North-East.mp4`** (frame-by-frame mean |diff| = 2.9 constant over all 150 frames vs the same video; both show the same street/rickshaws/cyclist) yet UI labels it "Outer Ring Road Bellandur Sample" (`index.html:1418-1420`). `Dataset/North-East.mp4` (174 MB, 170 s) has Bengali signage and a "SARKAR" bus — not Bengaluru ORR CCTV; no provenance in `Dataset/README.md` (video is gitignored). No Bengaluru traffic-camera footage exists in the repo.

## 5. CV evaluation audit — ABSENT
- No fine-tuning: no labels, annotations, `data.yaml`, training script, training logs, runs, ONNX/TensorRT, or second weight file. Only stock `yolo11n.pt`. Git history contains none (`git log --all`).
- No accuracy evaluation: no mAP/IoU/precision/recall/per-class report or script anywhere in repo or history. The 30+ CV tests assert *invariants* (blank frame → [] , class names valid, tracker preserves IDs on crafted boxes, density/PCU factor values), never accuracy (`tests/test_vision_detector.py`, `test_density.py`, `test_speed_estimator.py`, `test_incident_detector.py`, `test_vehicle_counter.py`, `test_phase_verification.py:53-87`). Test "motorcycle/bicycle detected" passes on one incidental frame.
- No ground truth: no per-frame counts, no incident labels, no speed radar/GPS reference, no density survey. No dashboard responsiveness benchmark (only pipeline `processing_fps` 27.9/38.1 is recorded).
- Committed CI artifact `traffic_system/artifacts/vision_jobs.json` at HEAD still contains the 120 s/274-vehicle/962-incident job — i.e. the unevaluated outputs are being treated as demo evidence.

## 6. Problem-statement scorecard (CV-relevant)
| requirement | status | evidence |
|---|---|---|
| #2 detect vehicle density via CV | **partial, demo-grade** | 2D occupancy runs; not physical density, ROI polygon ignored, no validation |
| "CV models detect and count vehicles" | **partial** | genuine detection on clear COCO objects (~38 % frame recall on Indian traffic); counting churns/miscounts |
| "vehicle detection accuracy" evaluation | **missing** | no annotations/mAP/eval script/report |
| "accident alerts" | **present but noise** | 962 incidents/120 s, 59 % pedestrians, 87 % impossible magnitudes, UI shows 0 |
| data from "traffic cameras" | **missing** | only uploaded non-Bengaluru clips; no RTSP/CCTV/live source |
| "live visualization" | **partial** | annotated MP4 playback after batch job; no streaming |
| dashboard responsiveness | **unmeasured** | no latency benchmark; batch pipeline ~28–38 fps on MPS |
| calibration required for physical units | **missing** | homography/calibration unreachable via API/UI (dead code) |

## 7. Severity-ranked gaps (with file:line)
- **S1 CRITICAL — no evaluated detector for Indian traffic.** Stock COCO YOLO11n, no auto-rickshaw class, ~38–45 % frame recall on mixed Indian traffic, all rickshaws wrong-class; no mAP/precision/recall/annotations anywhere. `detector.py:22-35`, `traffic_system/computer_vision/*`, `tests/*` (no accuracy assertions).
- **S2 CRITICAL — speed uncalibrated yet presented as km/h and fed into prediction/actuation; calibration dead code.** `speed_estimator.py:19-23,43-44,143-159`; `vision_routes.py:331-336`; `bridge.py:717,773`; `README.md:359`.
- **S3 CRITICAL — "accident alerts" are noise with no plausibility clamp, no vehicle-only gating, no GT.** `incident_detector.py:23-38,89-175`; pipeline loop over all classes incl. pedestrians `video_processor.py:316-330`; committed artifact 962 incidents/120 s; UI hides them (`app.js:5709`).
- **S4 HIGH — density is an area heuristic, ROI polygon ignored, UI fabricates veh/km.** `density_estimator.py:28,37,39-99`; `app.js:5682-5686`; `index.html:1532`.
- **S5 HIGH — tracker/counter integrity (duplicate + under-count, min_hits=1, newborn-LOST, recovery window 5 frames, fake diagnostics).** `tracker.py:99,169-179,196-249`; `vehicle_counter.py:23,96-106,128-140`; `video_processor.py:126`.
- **S6 HIGH — PCU/hour extrapolated from 5–9 s windows, auto factor unreachable, pedestrians priced in live path.** `pcu_converter.py:24-60,71-100`; `video_processor.py:372-381`; `vision_routes.py:565-582`.
- **S7 MEDIUM — "closed-loop" is not causal: CV counts/PCU/incidents ignored; volume = static baseline × occupancy; fabricated defaults; provenance "Live Optical CCTV AI".** `bridge.py:703-785`; `traffic_physics.py:85-93`; `app.js:5727-5783`.
- **S8 MEDIUM — no live camera ingestion; live-frame client function undefined; samples mislabeled/non-Bengaluru (Seville + North-East excerpt).** `app.js:5878`; `index.html:1418-1420`; `app/static/*.mp4`; `Dataset/North-East.mp4`.
- **S9 MEDIUM — UI/README overclaims (ByteTrack, calibrated homography, Greenshields veh/km), incident counter always 0, sample_telemetry truncated to 40 rows.** `README.md:312,359,412`; `video_processor.py:3,469`; `index.html:1336`; `app.js:5709`.
- **S10 LOW — `id_switches_prevented` counts pedestrian/vehicle overlap; `/api/vision/status.target_classes` omits bicycle; simulation_mode API-only and hidden in UI; `job.model_name` reads nonexistent "engine" key.** `tracker.py:178-179`; `vision_routes.py:495`; `job_manager.py:223`.

## 8. What is genuinely working
- Real Ultralytics YOLO11n inference (MPS detected, CPU fallback) with **no synthetic fallback in normal mode**; raises typed errors when YOLO unavailable/corrupt video; output MP4 verified openable, H.264 transcode; ~28–38 fps on MPS 720p.
- Correct near-field detection of COCO classes: bus (0.67–0.79), cars on motorway, pedestrians, bicycles, motorcycles; threshold honored.
- Solid engineering around the model: chunked 256 MB upload + SHA-256, async job queue/persistence, ownership/auth boundaries, video streaming with Range support, atomic job state, honest JSON provenance flags (`UNCALIBRATED_PROXY`, `heuristic_optical_occupancy`, `is_actual_measured_hourly_flow:false`) and UI calibration footnote.
- Indo-HCM PCU factor table values are plausible and citable; annotated video HUD is real.
- All of this is **M1 demo**: it detects objects, it does not measure traffic.

## 9. Minimum credible path to satisfy the problem statement (CV part)
**P0 — truth-in-labeling (1–2 days):** fix incident key mismatch, remove/relabel "veh/km"/"Greenshields"/"calibrated speed"/ByteTrack claims; show `is_calibrated=false` badges; fix undefined live-loop export; label samples with true provenance. Zero new tech.
**P1 — evaluated Indian-traffic detector (2–3 weeks, long pole = annotation):**
1. Target classes: car, two-wheeler, auto-rickshaw, bus, LCV/truck, pedestrian/cyclist.
2. Get 3–5 real Bengaluru camera clips (BTP/open CCTV or recorded ORR footage); if unavailable, use a public Indian traffic dataset and state the domain gap explicitly.
3. Label 1,500–3,000 frames across clips; **video-level train/val/test split**.
4. Fine-tune YOLO11s/m (`imgsz 960–1280`, ~60–100 epochs) on the 6-class set; keep stock model as baseline.
5. Ship `scripts/eval_cv.py` + committed `eval/detection_report.json|md`: mAP50, mAP50-95, per-class P/R/F1, count error vs manual GT per clip, tracking IDF1/MOTA. This is the problem-statement's "vehicle detection accuracy" deliverable.
**P2 — make measurements honest (1–2 weeks):**
- Counting: track-confirm ≥3 hits; Kalman/ByteTrack-style motion model (or `model.track(persist=True)`), fix newborn-LOST bug, no counting of single-frame tracks; count only **line-crossings** for flow; exclude parked/stationary from flow; dedupe IDs.
- Speed: per-camera 4-point homography via new `POST /api/vision/cameras/{id}/calibrate` + UI; store `camera_config` and pass into job (`vision_routes.py:331-336`); validate vs GPS/radar on ≥2 clips; otherwise remove speed from KPI/prediction/Webster.
- Density: honor ROI polygons (lane polygons), or calibrate ROI ground area per camera to report veh/km/lane; validate occupancy vs manual GT (MAE/R²); delete UI `PCU/h ÷ speed` density.
- Incidents: vehicle classes only, active-lane polygon, dwell hysteresis, |decel| ≤ 8–10 m/s² clamp, dedup per track; relabel as "hard-braking advisory (uncalibrated)" until precision/recall measured on labeled incident clips (required before claiming "accident alerts").
- PCU: only for windows ≥5 min, or present as sample estimate with CI; add auto-rickshaw class so 0.8 factor is reachable; never price pedestrians as PCU.
**P3 — wire validated CV into prediction (2–3 days):** replace static-baseline volume with measured flow (PCU/h) + occupancy mapping; remove fabricated defaults; tag telemetry with camera id, clip timestamp, model version, calibration state; only allow actuation from calibrated cameras.
**P4 — evaluation & report (2 days):** detection accuracy (P1 metrics), density/occupancy validation, incident precision/recall, end-to-end dashboard latency benchmark; commit results and put them in the report/UI.

Reproduce: `/tmp/cv_audit/run_pipeline.py` (end-to-end), `experiments.py` (unit evidence), `instrument_incidents.py` (speed→incident mechanism), `raw_detect.py` (frame sampling), outputs in `/tmp/cv_audit/out/`.

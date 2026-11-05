# Project Structure & Plain-English Guide

> **Current status:** functional capstone prototype, not production. Read [`docs/AUDIT_REPORT.md`](docs/AUDIT_REPORT.md) for evidence and [`docs/VISION.md`](docs/VISION.md) for the target. This guide explains what the folders do and what is safe to trust.

---

## 1. The system in one paragraph

The project has three layers: **see**, **forecast**, and **decide**. The *see* layer is computer vision: a video is uploaded, YOLO detects objects, a tracker follows them, and the system estimates counts, occupancy, speed, and incidents. The *forecast* layer uses an XGBoost model to predict next-hour congestion. The *decide* layer computes Webster signal-timing advisories and alternate routes. A web dashboard presents these layers to a Traffic Management user and a Road User.

At present the layers exist but are uneven:
- The forecast/routing/signal engineering is real and testable.
- The CV layer runs genuine YOLO inference but is **not yet a validated traffic-measurement system**.
- The UI is being repaired; some old labels and tabs are inaccurate.

---

## 2. Folder-by-folder

| Path | What it is | What to know |
|---|---|---|
| `app/server.py` | Custom `ThreadingHTTPServer` + REST routes | Serves the UI and APIs; auth/route fixes are in Phase 0 |
| `app/routes/vision_routes.py` | Upload, job, results, live-frame/actuation handlers | CV job ownership/auth is real; “actuation” is heuristic |
| `app/static/` | **Canonical** frontend source | HTML/CSS/JS; `public/` is a generated mirror |
| `public/` | Static hosting mirror | Generated from `app/static`; do not hand-edit |
| `api/index.py` | Vercel serverless entry | Limited; cannot run the CV workload |
| `run_system.py` | Bootstrapper | Pre-flight checks + server; use a free port |
| `traffic_system/computer_vision/` | Detector, tracker, counter, speed/density/incident, job manager | Genuine inference; uncalibrated measurements; M1 status |
| `traffic_system/core/` | Entities, road registry, physics, security, time/fs | Shared foundation; some live defaults need fixing |
| `traffic_system/models/` | XGBoost predictor + pure-Python tree inference | Real 86.98% on synthetic benchmark; baselines in audit |
| `traffic_system/routing/` | Dijkstra/BPR navigator | Works on a simplified 24-corridor graph |
| `traffic_system/simulation/` | Greenshields counterfactual + Webster optimizer | Advisory formulas; inputs currently often derived |
| `traffic_system/live/` | TomTom/Open-Meteo bridge and fallbacks | Providers misconfigured; fallback is labelled |
| `traffic_system/events/` | Municipal event lifecycle | Real JSON event store; used by route context |
| `traffic_system/integrations/` | TomTom, Google Maps, weather, API manager | Google browser map works; live status needs config fix |
| `traffic_system/storage/` | Video/chunk storage | Upload/job flow works; tests must not write here |
| `traffic_system/synthesizer/` | Internal synthetic stress/snapshot tooling | Not a product feature; remove from main UI |
| `traffic_system/junction/`, `dispatch/` | Junction telemetry and action recommendations | Used by authority views; some values hardcoded |
| `traffic_system/artifacts/` | Model/topology artifacts + seed data | Some files are runtime state and should move out of git |
| `Dataset/` | 57,600-row synthetic hourly benchmark | Read [`Dataset/README.md`](Dataset/README.md) before citing it |
| `Literature/` | Reference papers | Academic background, not runtime data |
| `architecture/` | Diagrams and architecture notes | Some stale claims; VISION/AUDIT are authoritative |
| `scripts/` | Demonstrators, static sync, utilities | `demonstrate_bengaluru_video.py` needs a running server |
| `tests/` | Pytest unit/integration suite + Playwright scripts | Heavy video test is opt-in; CI in `.github/workflows/ci.yml` |
| `docs/` | VISION, AUDIT, requirements, evidence, archive | Source of truth for product/current state |

---

## 3. What is safe to trust today

- **Model accuracy claim:** 86.98% chronological holdout is reproducible from the committed artifacts on the committed synthetic CSV. It is **not** evidence of real-Bengaluru accuracy, and it is only +0.22pp over a lookup baseline.
- **Upload/job engineering:** chunked upload, SHA-256, ownership checks, job persistence, annotated video output, HTTP Range streaming.
- **Routing/signal formulas:** Dijkstra/BPR and Webster are implemented and unit-tested, but their current inputs/route geometry are simplified.
- **Detection:** YOLO11n genuinely runs on uploaded clips; it detects common COCO classes. It does **not** detect auto-rickshaws as a class and is not evaluated for accuracy.
- **UI:** you can log in, plan a route, upload a clip, see progress/results, and view a map. The header/nav, heat overlay, auth, and several labels are under repair.

**Do not trust without checking:** “ByteTrack”, “CoreML”, “XGBoost 15m”, “calibrated speed”, “Greenshields density”, “Live Optical CCTV AI”, “OFFICIAL_VERIFIED” events created without auth, and any volume/prediction that does not trace to a measured input. These are known audit findings.

---

## 4. Run it

```bash
pip install -r requirements.txt
python3 run_system.py 8090
# open http://127.0.0.1:8090
```

Development demo accounts (non-production only, when `ALLOW_DEMO_ACCOUNTS=true`):
- `admin` / `Admin@123` — Traffic Management
- `commuter` / `Admin@123` — Road User

Set `ADMIN_USERNAME` / `ADMIN_PASSWORD` and disable demo accounts for any real deployment.

## 5. Test it

```bash
pytest -m "not integration"   # fast, CI path
pytest                         # fast; heavy video + live-API integration tests skip by default
```

The heavy `North-East.mp4` test is opt-in (`RUN_HEAVY_VIDEO_TEST=1 pytest -m integration`) and must not mutate tracked artifacts or storage. The fast suite is 217 collected / 213 passed / 4 skipped by default. See `tests/conftest.py` and `pytest.ini`.

## 6. The target (short version)

1. Camera/clip → camera registry + calibration + ROI/lane polygons.
2. Fine-tuned Indian-traffic detector → ByteTrack/BoT-SORT → confirmed tracks → line-crossing counts.
3. `TrafficMeasurement` contract (counts, flow, occupancy, calibrated/proxy speed, incidents, provenance).
4. XGBoost next-hour forecast from measured features + published baselines.
5. Webster advisory + route advisory from measured state.
6. Dashboard: Monitor / Predict / Decide / Trip + Evaluation page.
7. Evidence: detection mAP, count error, speed/density/incident validation, prediction metrics, dashboard latency.

Read [`docs/VISION.md`](docs/VISION.md) for the full contract, roadmap, and acceptance gates.

---

## 7. Glossary

| Term | Meaning |
|---|---|
| **CV** | Computer vision; in this project, detecting/tracking vehicles in video |
| **YOLO** | “You Only Look Once” object detector; current weights are stock COCO, not fine-tuned for Indian traffic |
| **mAP** | Mean average precision; the required detection-accuracy metric, currently missing |
| **Tracker** | Associates detections across frames; current implementation is a custom IoU tracker, not ByteTrack |
| **PCU** | Passenger Car Unit; converts mixed vehicle types to car-equivalents |
| **Occupancy** | Share of a camera ROI covered by vehicle bounding boxes; not the same as veh/km |
| **Calibration/homography** | Mapping camera pixels to ground meters; required for physical speed/density |
| **XGBoost** | Gradient-boosted tree classifier used for next-hour congestion |
| **Baseline** | A trivial comparison (majority, persistence, lookup) used to judge the ML model |
| **Provenance** | Where a value came from: live, cached, historical, simulated, proxy |
| **Webster** | Classic formula for minimum-delay signal cycle/green splits; advisory only |
| **BPR** | Bureau of Public Roads delay formula used for route impedance |
| **Dijkstra** | Shortest-path algorithm used for alternate routes |

---

## 8. Where to start reading

1. [`docs/VISION.md`](docs/VISION.md) — target and rules.
2. [`docs/AUDIT_REPORT.md`](docs/AUDIT_REPORT.md) — current truth and defects.
3. [`README.md`](README.md) — quickstart and honest status.
4. `traffic_system/computer_vision/` — the layer that most needs work.
5. `traffic_system/models/predictor.py` — the forecast model and its defaults.
6. `app/static/app.js` / `index.html` — the dashboard being repaired.

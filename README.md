# Smart Traffic AI — Camera-First Traffic Understanding (Capstone Prototype)

An AI-based traffic monitoring and congestion-prediction project for Bengaluru-style mixed traffic. The product direction is set in [`docs/VISION.md`](docs/VISION.md); the current-state evidence and defects are in [`docs/AUDIT_REPORT.md`](docs/AUDIT_REPORT.md). The official problem statement is [`docs/requirements/378_Design Project Problem Statement_6_Rashmi Mothkur.docx`](docs/requirements/378_Design%20Project%20Problem%20Statement_6_Rashmi%20Mothkur.docx).

> **Current status (2026-11-04): functional single-node prototype, not production.**
> - ML congestion forecast: reproducible 86.98% on a **synthetic** 57,600-row benchmark; only +0.22pp over a `(road, hour, current LOS)` lookup. See [`docs/AUDIT_REPORT.md`](docs/AUDIT_REPORT.md).
> - Computer vision: **M1 “stock-detector demo.”** Genuine YOLO11n inference runs, but detection/counting/speed/density/incidents are uncalibrated and not evaluated. Vehicle-detection accuracy (a required deliverable) is not yet measured.
> - UI/API: broad demo surface with known responsive, auth, routing, and data-integrity defects. Phase 0 remediation is in progress.
> - Phase 0 verified: 1280–1920 responsive shell, no console errors, role-gated tabs, anonymous admin writes 401, fast suite 213 pass / 4 skip. CI added; deployment verification remains Phase 4.

---

## What this repository actually contains

| Layer | Current implementation | Honest status |
|---|---|---|
| Web app | Python `ThreadingHTTPServer` + vanilla HTML/CSS/JS | Working prototype; Phase 0 UI fixes in progress |
| CV | Ultralytics YOLO11n (stock COCO) + custom IoU tracker + occupancy/speed/incident heuristics | Genuine inference; **not a validated traffic-measurement system** |
| ML | XGBoost 4-class next-hour classifier + pure-Python tree inference; local attribution is **Decision Tree Path Attribution**, not TreeSHAP | Real and reproducible; synthetic benchmark; baseline caveat |
| Routing | Dijkstra + BPR on a 24-corridor graph | Working prototype; route geometry simplified |
| Signals | Webster advisory cycle/green split | Formula implemented; inputs often derived, not measured |
| Data | 57,600-row Bengaluru-themed synthetic hourly benchmark (24 corridors, 8 zones, 2022) | Counts valid; content synthetic; see [`Dataset/README.md`](Dataset/README.md) |
| Integrations | Google Maps/Places, TomTom, Open-Meteo | Google browser map works; TomTom/weather config currently broken and fall back |

Signal and route outputs are **Advisory** only; the platform does not actuate physical traffic lights.

The 24-corridor/8-zone/57,600-row numbers are real for the committed CSV. They are **not** “real Kaggle observations”; the generator relation is documented in [`docs/AUDIT_REPORT.md`](docs/AUDIT_REPORT.md#5-mldata-findings).

---

## Quickstart

### Requirements
- Python 3.11+ (tested locally on 3.14)
- `pip install -r requirements.txt`
- Optional: FFmpeg for browser-compatible video transcoding
- Optional: valid Google Maps/TomTom keys in `.env` for map/live integrations

### Run
```bash
# Prefer a free port; 8080/8081 may be in use by other services.
python3 run_system.py 8090
```

Open `http://127.0.0.1:8090`.

Development demo accounts (only when `ALLOW_DEMO_ACCOUNTS=true` and not production):
- `admin` / `Admin@123` — Traffic Management
- `commuter` / `Admin@123` — Road User

For a real deployment, set `ADMIN_USERNAME`/`ADMIN_PASSWORD` and disable demo accounts. Do not use the development credentials in production.

### Test
```bash
pytest -m "not integration"   # fast unit suite; heavy video test excluded
pytest                         # fast; live-API and heavy video tests skip by default
```

The fast suite is the documented CI path. The current suite collects 217 tests: 213 pass in the fast path, 3 live-API tests are skipped by default, and the heavy North-East video test is opt-in (`RUN_HEAVY_VIDEO_TEST=1 pytest -m integration`). The old README’s “180 passing” log was stale. The heavy `North-East.mp4` test is marked integration and must not write tracked files.

### Useful scripts
```bash
python3 scripts/demonstrate_pipeline.py   # terminal ML/routing/signal walkthrough
python3 scripts/demonstrate_bengaluru_video.py  # chunked upload + YOLO demo (needs a running server)
python3 scripts/sync_static.py --check    # verify generated public/ mirror
```

---

## Documentation map

| Document | Purpose |
|---|---|
| [`docs/VISION.md`](docs/VISION.md) | Product vision, measurement contract, roadmap, evaluation gates |
| [`docs/AUDIT_REPORT.md`](docs/AUDIT_REPORT.md) | Brutal current-state audit with evidence |
| [`docs/PHASE0_VERIFICATION.md`](docs/PHASE0_VERIFICATION.md) | What Phase 0 changed and how it was verified |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | Required metrics and current evaluation gaps |
| [`docs/requirements/...docx`](docs/requirements/378_Design%20Project%20Problem%20Statement_6_Rashmi%20Mothkur.docx) | Official project statement (source of truth) |
| [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) | Plain-English repository and system guide |
| [`Dataset/README.md`](Dataset/README.md) | Dataset provenance, schema, and stale-results warning |
| [`architecture/SYSTEM_ARCHITECTURE_AND_FLOW.md`](architecture/SYSTEM_ARCHITECTURE_AND_FLOW.md) | Current architecture summary and target data flow |
| [`docs/archive/`](docs/archive/) | Old restructuring plan/notes kept for history, not current |

---

## System architecture (current, truthful)

```
Video upload / recorded clip
        │
        ▼
YOLO11n (stock COCO) ──► custom IoU tracker ──► bbox/ROI occupancy + proxy speed
        │                                               │
        │                                               ├─ incident heuristics (noisy, unvalidated)
        │                                               └─ PCU/hr extrapolation (short clips)
        ▼
CV job results (annotated MP4 + JSON)
        │
        └─ optional manual “apply measurements” ──► heuristic occupancy→volume mapping
                                                              │
                                                              ▼
                                              XGBoost next-hour classifier
                                                              │
                                                              ▼
                                     Webster signal advisory + Dijkstra route advisory
                                                              │
                                                              ▼
                                      Web dashboard (monitor / CV / map / decisions)
```

The target is to replace the heuristic CV→ML mapping with a measured `TrafficMeasurement` contract and to evaluate detection accuracy. See [`docs/VISION.md`](docs/VISION.md).

Historical benchmark data and provider feeds are **fallback/context**, not live measurements. Live failures are tagged, not silently replaced with fabricated values.

---

## Repository layout

```
app/                    Web server and static UI
  routes/               Vision/job HTTP handlers
  static/               Canonical frontend source (HTML/CSS/JS)
api/                    Vercel serverless entrypoint (limited; CV is not supported there)
architecture/           Diagrams and architecture notes
Dataset/                Benchmark CSV + provenance README
docs/                   VISION, AUDIT, requirements, evidence, archive
Literature/             Reference papers (PDFs)
scripts/                Demonstration, sync, and utility scripts
tests/                  Pytest unit/integration suite + Playwright scripts
traffic_system/         Core Python package
  computer_vision/      Detector, tracker, counter, density/speed/incident, job manager
  core/                 Entities, road registry, physics, security, time/fs utilities
  dispatch/             Action recommendations
  events/               Municipal event lifecycle
  integrations/         TomTom, Google Maps, weather, API manager
  junction/             Junction telemetry
  live/                 Live bridge and adapters
  models/               XGBoost predictor + pure-Python tree inference
  routing/              Dijkstra/BPR navigator
  simulation/           Greenshields counterfactual + Webster optimizer
  storage/              Video storage and migrations
  synthesizer/          Internal synthetic stress/snapshot tooling (not a product feature)
  artifacts/            Model/topology artifacts and seed data
run_system.py           CLI/server bootstrap + pre-flight checks
```

`app/static/` is canonical; `public/` is generated for static hosting. Runtime state should live outside tracked artifacts; Phase 0/4 moves it under an ignored data directory.

---

## Known limitations (must not be hidden)

1. **CV measurements are not validated.** No mAP/precision/recall or annotated dataset. Auto-rickshaws are not a detector class; counts/speed/density/incidents are demo-grade.
2. **The benchmark is synthetic.** The 86.98% accuracy is against a synthetic generator, not real Bengaluru observations; baselines are published in the audit.
3. **Live integrations are currently misconfigured.** TomTom/weather fall back to empirical baselines; do not present them as live.
4. **UI is under remediation.** Responsive nav, auth, routing, heat overlay, and labels are being fixed in Phase 0.
5. **Deployment is not verified.** Docker/Vercel claims need Phase 4 verification; Vercel cannot run the CV workload.
6. **The heavy video test is environment-dependent.** It must be skipped when its video is absent and must not mutate tracked files.

Do not add new claims to the UI or README unless they are backed by `docs/EVALUATION.md` or an equivalent committed measurement.

---

## Roadmap

- **M0 — truth reset:** docs, UI/nav, auth, tests, clean tree.
- **M1 — honest CV measurement:** Indian-traffic dataset/annotation, fine-tuned detector, tracking/counting, calibration, density/speed/incident validation, evaluation report.
- **M2 — measured CV → forecast:** `TrafficMeasurement` schema/state store, real capacity/flow mapping, baselines, remove fabricated defaults.
- **M3 — dashboard/evaluation:** Monitor/Predict/Decide views, evaluation page, responsiveness benchmark.
- **M4 — hardening/deployment:** clean repo, CI, Docker/Render verification, final evaluation.

See [`docs/VISION.md`](docs/VISION.md) for exits and metrics.

---

## License

MIT — see [`LICENSE`](LICENSE). Third-party notices include Ultralytics (AGPL-3.0) and OpenCV (Apache 2.0). The current YOLO weights are stock COCO weights; any fine-tuned weights must carry their dataset/model licence.

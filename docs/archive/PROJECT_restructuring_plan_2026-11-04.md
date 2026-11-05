# Project: Traffic AI Monitoring & Spatio-Temporal Prediction Repository Restructuring

## Architecture
- **AI & Spatio-Temporal Prediction Core (`traffic_system/`)**:
  - `core/`: Road network graph topology, speed estimation, congestion level classification.
  - `models/`: Random Forest & LightGBM multi-corridor congestion forecasting with physics features.
  - `vision/`: YOLOv11 vehicle detection, ByteTrack multi-object tracking, speed & throughput computation.
  - `live/`: Live TomTom traffic API and OpenWeatherMap telemetry data ingestion.
  - `simulation/`: Counterfactual traffic signal timing and scenario simulation.
  - `storage/`: SQLite database persistence, file storage manager, metadata registry.
  - `artifacts/`: Machine learning models and YOLO neural weights.
- **Web Interface & API Gateway (`app/` & `api/`)**:
  - `server.py`: FastAPI backend delivering REST endpoints, SSE streams, static file hosting.
  - `routes/`: Vision routes, job manager endpoints, health checks.
  - `static/`: Pure HTML5/ES6 frontend dashboard, tactile UI, Leaflet live maps, commuter console.
  - `api/index.py`: Serverless Vercel function gateway.
- **Data & Documentation (`data/`, `architecture/`)**:
  - `data/` (`Dataset/`): Bengaluru benchmark traffic CSV datasets.
  - `architecture/`: Technical architecture specifications, SVG/PNG diagrams, flowcharts, literature references.
- **Automation & Quality Assurance (`tests/`, `scripts/`)**:
  - `tests/`: Automated pytest test suite (38 test modules, 212 passed unit tests, 4 deselected integration tests).
  - `scripts/`: Video pipeline demonstrator, static synchronization, validation utilities.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Dead Video Cache Pruning | Purged ~1,200 MB leftover test videos in `traffic_system/storage/videos/{uploads,chunks,processed}/` keeping `.gitkeep` | M1 | Survey (E1, E3) |
| 2 | Artifact & Bytecode Cleanup | Reset inflated `vision_jobs.json` to `{}`, pruned orphaned `.pyc` and duplicate scripts | M1 | Survey (E1, E2) |
| 3 | Static Asset & Diagram Unification | Co-located architecture diagrams in root `architecture/` to prevent 404s, maintained static sync | M2 | Survey (E1, E3) |
| 4 | Clean Repository Restructuring | Reorganized scripts and root clutter into explicit, intuitive directories with backward-compatible forwarders | M2 | Survey (E2, E3) |
| 5 | Deployment & Invariant Preservation | Retained all paths tested by `tests/test_run_system_and_deployment.py` and ensured all modules import cleanly | M2 | Survey (E2) |
| 6 | Beginner & Non-Technical Documentation | Authored `PROJECT_STRUCTURE.md` explaining architecture using real-world command center analogies for beginners | M3 | Requirement R3 |
| 7 | Concurrency Isolation & Port Safety | Ensured Tomcat PID 1406 (ports 8080/8005) and Python PID 3116 (port 8081) are strictly untouched | M4 | Requirement R4 |
| 8 | Automated Pytest & Forensic Audit | Verified all 212 unit tests pass and obtained clean Forensic Integrity Audit verdict | M4 | Requirement R1-R4 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Dead Code & Storage Bloat Pruning | Prune 1.2 GB test video bloat, reset test artifact, clean orphaned bytecode | none | DONE |
| M2 | Explicit Repository Restructuring | Organize directory layout, co-locate architecture diagrams, maintain path contracts | M1 | DONE |
| M3 | Beginner & Non-Technical Architecture Documentation | Create comprehensive `PROJECT_STRUCTURE.md` and link in `README.md` | M2 | DONE |
| M4 | E2E Test Verification & Forensic Audit | Run pytest suite (212 tests pass), audit concurrency isolation, verify clean forensic audit | M3 | DONE |

## Interface Contracts
### `app/server.py` ↔ `architecture/`
- `app/server.py` mounts `/architecture` to `BASE_DIR / "architecture"`.
- Root `architecture/` contains `system_architecture_flowchart.svg` and `system_architecture_flowchart.png` so requests to `/architecture/*.png` and `/architecture/*.svg` return HTTP 200.

### `tests/test_run_system_and_deployment.py` Invariant
- Root files required: `render.yaml`, `vercel.json`, `Procfile`, `requirements.txt`, `LICENSE`, `README.md`, `.gitignore`, `api/index.py`.

### Concurrency Safety Invariant
- Ports 8080, 8005 (Tomcat) and 8081 (Python) must never be killed, stopped, or bound by any test or worker.

## Code Layout
```
/Users/ak/Documents/Dp-01/
├── app/
│   ├── routes/
│   ├── static/
│   └── server.py
├── architecture/
│   ├── system_architecture_flowchart.png
│   ├── system_architecture_flowchart.svg
│   ├── SYSTEM_ARCHITECTURE_AND_FLOW.md
│   └── ...
├── api/
│   └── index.py
├── data/ (Dataset/)
│   └── *.csv
├── scripts/
│   ├── __init__.py
│   ├── sync_static.py
│   ├── demonstrate_pipeline.py
│   └── demonstrate_bengaluru_video.py
├── tests/
│   └── ...
├── traffic_system/
│   ├── core/
│   ├── models/
│   ├── vision/
│   ├── live/
│   ├── simulation/
│   ├── storage/
│   └── artifacts/
├── PROJECT_STRUCTURE.md
├── README.md
├── requirements.txt
└── run_system.py
```

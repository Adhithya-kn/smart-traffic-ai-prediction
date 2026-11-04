# Smart Traffic AI: Spatio-Temporal Congestion Prediction, Simulation & Advisory Decision Support System

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![XGBoost 2.0+](https://img.shields.io/badge/XGBoost-2.0%2B-orange.svg)](https://xgboost.readthedocs.io/)
[![Architecture: Dual-Persona](https://img.shields.io/badge/Architecture-Dual--Persona-purple.svg)](#dual-persona-console-experience)
[![Simulation: Greenshields](https://img.shields.io/badge/Simulation-Greenshields%20Hydrodynamics-blue.svg)](#macroscopic-greenshields-policy-simulation)
[![Signals: Webster Advisory](https://img.shields.io/badge/Signals-Webster%20Advisory-green.svg)](#microscopic-webster-signal-optimization)
[![Tests: 180 Passing](https://img.shields.io/badge/Tests-180%20Passing%20(3%20skipped)-brightgreen.svg)](#automated-test-suite--verification)

> **Spatio-Temporal Intelligent Transportation Operating System (ST-ITOS)**  
> Grounded in a 57,600-record benchmark dataset across **24 arterial corridors and 8 urban zones in Bengaluru**, powered by **chronologically validated XGBoost gradient boosting**, **decision-tree path feature attribution**, **Greenshields macroscopic hydrodynamic flow simulation**, **Webster delay signal optimization recommendations**, and **dynamic Dijkstra detour routing**. Featuring an **Apple HIG tactile dual-console interface** connecting everyday commuters with municipal traffic managers.

---

### Important Operational Invariants & Provenance Disclaimers
* **Advisory & Simulation Platform**: This system provides decision support, simulated Webster signal timing recommendations, and traveler route advisories. It does **not** autonomously actuate real-world Bengaluru traffic lights, which requires physical municipal controller (SCATS/CoSiSys) integration.
* **Dataset Provenance**: The primary training benchmark consists of 57,600 records across 24 Bengaluru corridors with daily observation aggregates.
* **Model Features**: The trained XGBoost model utilizes volume, speed, capacity utilization, hour, day of week, weekend indicator, corridor ID, and city zone. Weather variables are not part of the active trained feature schema.
* **Explainability Methodology**: Prediction explanations are computed via exact decision tree split path feature attribution across the boosted ensemble, providing transparent local root-cause rankings.

---

## Table of Contents
1. [System Architecture Diagram](#system-architecture-diagram)
2. [End-to-End Traffic Pipeline & Component Flows](#end-to-end-traffic-pipeline--component-flows)
   - [Flow 1: Commuter Real-Time Trip Evaluation & Dynamic Detour Flow](#flow-1-commuter-real-time-trip-evaluation--dynamic-detour-flow)
   - [Flow 2: Spatio-Temporal Prediction & Feature Attribution Pipeline](#flow-2-spatio-temporal-prediction--feature-attribution-pipeline)
   - [Flow 3: Macroscopic Greenshields & Advisory Webster Signal Flow](#flow-3-macroscopic-greenshields--advisory-webster-signal-flow)
   - [Flow 4: Traffic Authority Incident Management & Policy Simulation Lifecycle](#flow-4-traffic-authority-incident-management--policy-simulation-lifecycle)
3. [Technology Stack Matrix](#technology-stack-matrix)
4. [Dual-Persona Console Experience](#dual-persona-console-experience)
5. [Core Engineering & Algorithmic Modules](#core-engineering--algorithmic-modules)
6. [Repository File & Directory Structure](#repository-file--directory-structure)
7. [Quickstart & Reproduction Guide](#quickstart--reproduction-guide)
8. [Automated Test Suite & Verification](#automated-test-suite--verification)

---

## System Architecture Diagram

The system operates as an integrated transportation analytics and simulation platform connecting municipal traffic authorities with everyday road users through calibrated telemetry ingestion, gradient-boosted spatial inference, and hydrodynamic counterfactual policy evaluations.

```
+========================================================================================================================+
|                                  SMART TRAFFIC AI: FULL SYSTEM ARCHITECTURE TOPOLOGY                                   |
+========================================================================================================================+

                                               +-----------------------------+
                                               |   TRAFFIC TELEMETRY FEED    |
                                               |  57,600 Benchmark Records   |
                                               |   24 Corridors • 8 Zones    |
                                               +--------------+--------------+
                                                              |
                                                              v
                                               +-----------------------------+
                                               |  DATA INGESTION & PIPELINE  |
                                               |   - Feature Normalization   |
                                               |   - Chronological Split     |
                                               |   - Label Encoding (4 LoS)  |
                                               +--------------+--------------+
                                                              |
                                                              v
+------------------------------------------------------------------------------------------------------------------------+
|                                             PREDICTIVE INTELLIGENCE CORE                                               |
|                                                                                                                        |
|       +------------------------------------+                         +------------------------------------+            |
|       |     XGBOOST 2.0 CLASSIFIER         |                         |   TREE-PATH ATTRIBUTION ENGINE     |            |
|       |  8-Feature Spatio-Temporal Vector  |   Ensemble Path Split   |    Local Decision Route Impact     |            |
|       |  - Volume, Speed, Capacity Util    | ----------------------> |    - Top Congestion Drivers (%)    |            |
|       |  - Diurnal Schedule, Day of Week   |                         |    - Plain-English Root Causes     |            |
|       |  - Multi-Class Softmax (Low-Lat)   |                         |    - Deterministic Tree Traversal  |            |
|       +-----------------+------------------+                         +-----------------+------------------+            |
|                         |                                                              |                               |
|                         +------------------------------+-------------------------------+                               |
|                                                        |                                                               |
|                                                        v                                                               |
|                                      +-----------------------------------+                                             |
|                                      |      SHANNON ENTROPY GATE         |                                             |
|                                      |      H(p) = -SUM(p * log2(p))     |                                             |
|                                      |  Flags Epistemic Uncertainty >1.5 |                                             |
|                                      +-----------------+-----------------+                                             |
+--------------------------------------------------------|---------------------------------------------------------------+
                                                         |
                         +-------------------------------+-------------------------------+
                         |                                                               |
                         v                                                               v
+------------------------------------------------+             +------------------------------------------------+
|       DYNAMIC GRAPH DIJKSTRA DETOUR ENGINE     |             |     MACROSCOPIC GREENSHIELDS POLICY SIMULATOR  |
|                                                |             |                                                |
|  - Urban Adjacency Matrix (24 Corridors)       |             |  - Hydrodynamic Flow: q = k * v                |
|  - Bureau of Public Roads (BPR) Impedance:     |             |  - Demand Diversion: alpha (0.0 to 0.50)       |
|    W(e) = t0 * [1 + alpha * (V/C)^beta] + P    |             |  - Signal Coordination: beta (0.0 to 0.30)     |
|  - Dynamic Municipal Roadwork Penalty (P)      |             |  - Predicts Jam De-escalation & Relief %       |
|  - Real-Time Alternate Route Recommendation    |             |  - Advisory Webster Cycle Calculations         |
|  - Estimated Time Saved (Simulated Benefit)    |             |    C_0 = (1.5L + 5) / (1 - Y)                  |
+-----------------------+------------------------+             +-----------------------+------------------------+
                        |                                                              |
                        +-------------------------------+------------------------------+
                                                        |
                                                        v
+------------------------------------------------------------------------------------------------------------------------+
|                                    HIGH-PERFORMANCE MULTI-THREADED API DISPATCHER                                      |
|                                                (Python 3.11+ Native)                                                   |
|                                                                                                                        |
|       Endpoints:                                                                                                       |
|       - POST /api/auth/login              - POST /api/route/evaluate          - GET  /api/corridors/all                |
|       - POST /api/events/add              - POST /api/events/delete           - POST /api/simulation/run               |
|       - POST /api/vision/upload           - GET  /api/vision/jobs             - POST /api/synthesizer/stream/generate  |
|                                                                                                                        |
|       Serving Capabilities:                                                                                            |
|       * Multi-client concurrent request routing with sub-millisecond CPU forward passes                                |
|       * Real-time road network telemetry enrichment and corridor state propagation                                     |
|       * Dual-console role-based session management (Road User vs Traffic Control Room)                                 |
+-------------------------------------------------------+----------------------------------------------------------------+
                                                        |
                            +---------------------------+---------------------------+
                            |                                                       |
                            v                                                       v
+-------------------------------------------------------+     +----------------------------------------------------------+
|                  ROAD USER CONSOLE                    |     |            TRAFFIC AUTHORITY CONTROL ROOM                |
|               (Public Traveler Portal)                |     |                (Municipal Command Center)                |
|                                                       |     |                                                          |
|  [+] Exact Historical / Live Date Selector            |     |  [+] 8-Zone Citywide Heatmap & Real-Time LoS Breakdown   |
|  [+] 24-Hour Departure Time Input                     |     |  [+] Dynamic Event Lifecycle: Create, Schedule & Purge   |
|  [+] Predictive Level of Service (LoS) Classification |     |  [+] Real-Time Counterfactual Policy Sliders (alpha/beta)|
|  [+] Decision-Tree Path Congestion Attribution        |     |  [+] Advisory Webster Signal Allocations (g_NS, g_EW)    |
|  [+] Optimal Bypass Detour & Estimated Saved Minutes  |     |  [+] Automated MUTCD Variable Message Sign Broadcasts    |
|  [+] Apple HIG Specular UI & Tactile Micro-Haptics    |     |  [+] Synchronous Inter-Console State Propagation         |
+-------------------------------------------------------+     +----------------------------------------------------------+
```

---

## End-to-End Traffic Pipeline & Component Flows

### Flow 1: Commuter Real-Time Trip Evaluation & Dynamic Detour Flow
Traces a traveler query through route graph discovery, active event scanning, Bureau of Public Roads (BPR) impedance computation, and alternate bypass recommendation:

```
+---------------------------------------------------------------------------------------------------+
|                        COMMUTER TRIP EVALUATION & DYNAMIC DETOUR PIPELINE                         |
+---------------------------------------------------------------------------------------------------+

                          +------------------------------------------+
                          |           COMMUTER ROUTE QUERY           |
                          |  Origin Corridor: RD_BLR_01 (100 Ft Rd)  |
                          |  Destination:     RD_BLR_05 (Hebbal Fly) |
                          |  Departure Date:  2022-01-15, Time: 18:00|
                          +--------------------+---------------------+
                                               |
                                               v
                          +------------------------------------------+
                          |        MUNICIPAL EVENT INTERSECTION      |
                          | Check active incidents in candidate path |
                          | Match Found: Water Pipeline Trenching    |
                          | Schedule: 16:00 - 20:00 (Active Match)   |
                          +--------------------+---------------------+
                                               |
               +-------------------------------+-------------------------------+
               |                                                               |
               v                                                               v
+------------------------------+                               +------------------------------+
|     PRIMARY DIRECT ROUTE     |                               |   ALTERNATE DETOUR BYPASS    |
+------------------------------+                               +------------------------------+
| Corridor: RD_BLR_01 (Direct) |                               | Corridor: RD_BLR_02 (Bypass) |
| Distance: 4.8 km             |                               | Distance: 5.6 km             |
| Baseline Travel Time: 12 min |                               | Baseline Travel Time: 14 min |
| Event Penalty: +25 min delay |                               | Event Penalty: 0 min (Clear) |
|                              |                               |                              |
| BPR Edge Weight Calculation: |                               | BPR Edge Weight Calculation: |
| W(e) = t0 * [1 + 0.15*(V/C)^4|                               | W(e) = t0 * [1 + 0.15*(V/C)^4|
| Effective Time: 37.0 min     |                               | Effective Time: 17.5 min     |
+------------------------------+                               +------------------------------+
               |                                                               |
               +-------------------------------+-------------------------------+
                                               |
                                               v
                          +------------------------------------------+
                          |       PREDICTIVE LEVEL OF SERVICE        |
                          | Primary Route:   Severe Congestion (LoS F|
                          | Detour Route:    Moderate Flow (LoS C)   |
                          | Root Cause:      Capacity Constraint     |
                          |                  Evening Peak Rush       |
                          +--------------------+---------------------+
                                               |
                                               v
                          +------------------------------------------+
                          |        COMMUTER ADVISORY DELIVERED       |
                          | "Take Bypass via 80 Feet Road"           |
                          | Estimated Travel Time Saved: 19.5 min    |
                          | (Simulated Model Benefit Estimate)       |
                          +------------------------------------------+
```

### Flow 2: Spatio-Temporal Prediction & Feature Attribution Pipeline

```
+---------------------------------------------------------------------------------------------------+
|                        SPATIO-TEMPORAL INFERENCE & EXPLAINABILITY PIPELINE                        |
+---------------------------------------------------------------------------------------------------+

 Raw Sensor / Route Input:
 [ Volume: 2,420 veh/h ] [ Speed: 18.2 km/h ] [ Capacity Util: 82.4% ] [ Hour: 18 ] [ DayOfWeek: 3 ]
           |
           v
 [ Standard Scaler & Preprocessor ]
 Scale continuous numerical inputs & encode temporal schedule / corridor one-hot vectors
           |
           v
 [ XGBoost 2.0 Multi-Class Booster ] 
 Evaluates gradient boosted tree ensemble in sub-millisecond CPU pass
 Output: Softmax Probability Distribution [P(Low), P(Mod), P(High), P(Severe)]
           |
           +-----------------------------------------------+
           |                                               |
           v                                               v
 [ Argmax Congestion Label ]                     [ Decision Tree Path Attribution ]
 Determined Level of Service:                    Traverses split nodes to quantify feature impacts:
 "Severe Congestion (LoS F)"                     - Capacity Utilization: +42.1%
           |                                     - Peak Evening Commute: +36.5%
           |                                     - Kinematic Velocity: +21.4%
           |                                               |
           +-----------------------+-----------------------+
                                   |
                                   v
             [ Dispatcher Response Payload to Client ]
```

### Flow 3: Macroscopic Greenshields & Advisory Webster Signal Flow

```
+---------------------------------------------------------------------------------------------------+
|                     HYDRODYNAMIC SIMULATION & ADVISORY SIGNAL OPTIMIZATION                        |
+---------------------------------------------------------------------------------------------------+

 Traffic Operator Policy Inputs:
 [ alpha: Demand Diversion Rate (0-50%) ]   [ beta: Signal Coordination Progression (0-30%) ]
           |
           v
 [ Greenshields Continuity Transformer: q = k * v ]
 1. Effective Vehicle Demand:   q_post = q_baseline * (1 - alpha)
 2. Mean Corridor Velocity:     v_post = min(v_free_flow, v_baseline * (1 + beta))
 3. Road Segment Density:       k_post = q_post / v_post
           |
           v
 [ Re-evaluate 24 Arterial Corridors Post-Intervention ]
 Re-score through XGBoost engine -> Evaluates simulated de-escalation rate
           |
           v
 [ Microscopic Webster Signal Recommendation Formula ]
 1. Critical Phase Ratios:      y_NS = q_NS / s_NS,  y_EW = q_EW / s_EW,  Y = sum(y_i)
 2. Optimal Cycle Length:       C_0 = (1.5 * L + 5) / (1 - Y)   [bounded: 45s <= C_0 <= 150s]
 3. Effective Green Allocation: g_i = (y_i / Y) * (C_0 - L)      [min green >= 10s per IRC:93]
           |
           v
 [ Advisory Recommendations & Dynamic VMS Displays ]
 Transmits advisory recommendations for municipal traffic engineers (No autonomous physical actuation)
```

### Flow 4: Traffic Authority Incident Management & Policy Simulation Lifecycle

```
+---------------------------------------------------------------------------------------------------+
|                    TRAFFIC AUTHORITY COMMAND CENTER LIFECYCLE & MUTCD DISPATCH                    |
+---------------------------------------------------------------------------------------------------+

   [ Traffic Operations Center / Municipal Authority Console ]
                 |
                 +-----------------------------------------------+
                 |                                               |
                 v                                               v
   +------------------------------+               +------------------------------+
   |   INCIDENT INJECTION / PURGE |               |  POLICY SIMULATION LEVERS    |
   |  - Add Roadwork Permit       |               |  - Adjust Diversion Alpha    |
   |  - Define Schedule Window    |               |  - Adjust Signal Beta        |
   |  - Instant One-Click Deletion|               |  - Trigger Simulation Engine |
   +--------------+---------------+               +--------------+---------------+
                  |                                              |
                  +-----------------------+----------------------+
                                          |
                                          v
   +-----------------------------------------------------------------------------+
   |                       CENTRAL DISPATCH COORDINATOR                          |
   |  - Re-evaluates 24 Arterial Corridors in Indiranagar, Koramangala, etc.     |
   |  - Updates Corridor Adjacency Matrix & Bureau of Public Roads (BPR) Weights |
   |  - Broadcasts updated status to Commuter Road User navigation endpoints     |
   +--------------------------------------+--------------------------------------+
                                          |
                                          v
   +-----------------------------------------------------------------------------+
   |                    ADVISORY DIRECTIVES & MUTCD VMS MESSAGES                 |
   |  1. Advisory Webster Signals: Dynamic Recommended Phase Timing (g_NS / g_EW)|
   |  2. Arterial VMS Displays: Electronic Signs Post Real-Time Detour Guidance  |
   |  3. Congestion Heatmap: Instant Visual Updates Across All 8 City Zones      |
   +-----------------------------------------------------------------------------+
```

---

## Technology Stack Matrix

| Architecture Layer | Core Technology | Exact Specification | Role in System | Architectural Rationale & Why Chosen |
| :--- | :--- | :--- | :--- | :--- |
| **Language Runtime** | **Python** | 3.10+ / 3.11 / 3.14 Standard | Backend AI engine, pathfinding, physics | High performance, thread concurrency, unified scientific ecosystem |
| **Machine Learning Core** | **XGBoost** | XGBoost 2.0+ (`Booster`) | Spatio-temporal Level of Service classifier | Fast CPU inference, chronological date validation (**86.98% out-of-time accuracy**) across 4 Level of Service classes |
| **Explainable AI (XAI)** | **Decision Tree Path Attribution** | Ensemble node split analysis | Local feature impact attribution | Deterministic traversal of tree splits attributing prediction drivers without sampling variance |
| **Graph Routing Engine** | **Dynamic Dijkstra** | Dynamic Adjacency Matrix | Shortest path & alternate bypass navigation | Evaluates real-time BPR impedance and roadwork penalties across 24 corridors in sub-10ms |
| **Macroscopic Physics** | **Greenshields Model** | Hydrodynamics ($q = k \cdot v$) | Counterfactual policy simulation | Guarantees vehicle conservation; models citywide flow de-escalation |
| **Microscopic Signals** | **Webster's Formula** | Minimum Delay Cycle Length | Advisory traffic signal phase split optimization | Replaces static timers with delay-minimizing phase splits bounded by IRC:93 minimum green times ($\ge 10\text{s}$) |
| **Computer Vision Core** | **Ultralytics YOLO & OpenCV** | YOLO11 / ByteTrack / Headless CV | Video vehicle detection, tracking, PCU conversion | Real vehicle counting, speed estimation, and spatial incident detection |
| **Data Engine** | **Pandas & NumPy** | Pandas 2.2+, NumPy 2.0+ | Ingestion, feature scaling, matrices | Grounded in a 57,600-record benchmark across 24 Bengaluru corridors |
| **Web Server Layer** | **`ThreadingHTTPServer`** | Python Native Standard Library | Concurrent REST API Gateway | Multi-threaded client dispatch with zero heavy framework bloat and low memory footprint |
| **Frontend Presentation**| **Vanilla HTML5 & CSS3** | Apple HIG Dark Obsidian Palette | Tactile, responsive dual consoles | Deep obsidian accents (`#07080a`), specular top borders, spring physics (`cubic-bezier(0.16, 1, 0.3, 1)`) |
| **Client Visualization** | **Chart.js** | Chart.js 4.4 UMD | Interactive policy comparison charts | Sub-millisecond rendering with fixed layout dimensions preventing Cumulative Layout Shift |
| **Micro-Haptic Engine** | **Web Audio API** | Native Browser `AudioContext` | Real-time synthesized acoustic chimes | Delivers instant tactile confirmation for user actions without external asset loading |
| **Automated Testing** | **Pytest & Playwright** | Pytest 9.1+, Playwright 1.48+ | Unit invariants, API, & end-to-end automation | 183 automated test cases verifying mathematical invariants, security, and parallel console interactions |

---

## Dual-Persona Console Experience

### 1. Commuter Road User Portal
Designed for travelers seeking reliable trip forecasting, congestion avoidance, and clear explanations:
* **True Date & Time Selector**: Seamlessly evaluates trips matching the chronological data horizon (`2022-01-01` to `2022-03-31` / current).
* **Predictive Congestion Level**: Displays real-time risk classification (`Low`, `Moderate`, `High`, `Severe`).
* **Root-Cause Attribution Narrative**: Explains the top drivers behind corridor congestion (e.g., *"Capacity Constraint 42%, Evening Peak 36%"*).
* **Dynamic Smart Detour**: Automatically calculates alternate bypass routes with estimated minutes saved (e.g., *via 80 Feet Road, saving 19.5 mins*).

### 2. Traffic Management Authority Command Center
Engineered for municipal engineers, signal technicians, and emergency dispatchers:
* **8-Zone Metropolitan Heatmap**: Instant high-contrast visibility across Indiranagar, Koramangala, Whitefield, HSR Layout, Electronic City, Jayanagar, Marathahalli, and Hebbal.
* **Dynamic Event Lifecycle**: Inject construction permits, lane closures, and stadium events with immediate network-wide propagation and instant one-click deletion.
* **Counterfactual Policy Simulator**: Interactive sliders for demand diversion ($\alpha$) and signal progression ($\beta$) calculating simulated corridor relief.
* **Advisory Webster Signal Splits**: Computes optimized green times ($g_{\text{NS}}, g_{\text{EW}}$) and generates automated MUTCD Variable Message Sign (VMS) broadcasts.

---

## Core Engineering & Algorithmic Modules

### 1. Spatio-Temporal Prediction (`traffic_system/models/`)
* **`predictor.py`**: Loads trained XGBoost weights and preprocessor scalers, evaluates feature vectors, computes tree-path feature attributions, and computes Shannon entropy $H(p)$ to flag epistemic uncertainty.

### 2. Dynamic Routing & Detour Engine (`traffic_system/routing/`)
* **`navigator.py`**: Builds directed graph topology across 24 arterial corridors and 8 urban zones. Computes travel times using the Bureau of Public Roads (BPR) impedance formula:
  $$W(e) = t_0 \cdot \left[ 1 + \alpha_{\text{BPR}} \left( \frac{V_e}{C_e} \right)^{\beta_{\text{BPR}}} \right] + \text{Penalty}_{\text{event}}$$

### 3. Macroscopic Simulation & Webster Actuation (`traffic_system/simulation/`)
* **`counterfactual.py`**: Implements Greenshields hydrodynamic flow continuity ($q = k \cdot v$), modeling policy interventions and recalculating post-action congestion states.
* **`signal_optimizer.py`**: Computes Webster minimum-delay optimal signal cycle length recommendations:
  $$C_0 = \frac{1.5 L + 5}{1 - Y}, \quad g_i = \frac{y_i}{Y} (C_0 - L)$$
  Clamped between 45s and 150s with IRC:93 minimum green time ($\ge 10\text{s}$).

### 4. Computer Vision Intelligence (`traffic_system/computer_vision/`)
* **`detector.py`**: Ultralytics YOLO vehicle detection with strict empty frame and non-synthetic inference guarantees.
* **`tracker.py`**: Multi-object ByteTrack spatial-temporal trajectory association.
* **`incident_detector.py`**: Kinematic detection of stalled vehicles, wrong-way drivers, and deceleration shockwaves.
* **`speed_estimator.py` & `density_estimator.py`**: Calibrated homography speed estimation and road ROI occupancy calculation.

### 5. Synthesizer & Snapshot Storage (`traffic_system/synthesizer/`)
* **`stream_generator.py`**: Explicitly labeled synthetic telemetry and scenario stress testing with reproducible PRNG seeds.
* **`storage_manager.py`**: POSIX atomic snapshot backup, SHA-256 integrity verification, path traversal prevention, and secret masking.

---

## Repository File & Directory Structure

```
smart-traffic-ai/
├── .dockerignore                       # Container build exclusions for rapid lean builds
├── .gitignore                          # Clean gitignore excluding caches, videos, credentials, backups
├── Dockerfile                          # Lightweight Python 3.11 container manifest with FFmpeg/OpenCV
├── LICENSE                             # MIT License & Third-Party Open Source Notices
├── Procfile                            # Cloud process declaration (python3 run_system.py)
├── README.md                           # Master system specification & technical blueprint
├── render.yaml                         # Render Infrastructure-as-Code deployment blueprint with persistent disk
├── requirements.txt                    # Pinned production Python runtime dependencies
├── run_system.py                       # CLI bootstrapper with pre-flight diagnostics & port resolution
├── vercel.json                         # Vercel serverless routing, execution limits, and memory config
├── Dataset/                            # Benchmark metropolitan traffic datasets
│   └── Banglore_traffic_Dataset.csv    # 57,600 benchmark records across 24 corridors & 8 zones
├── api/                                # Serverless execution layer
│   └── index.py                        # Vercel serverless HTTP handler entrypoint
├── app/                                # Application server and client web interfaces
│   ├── server.py                       # Multi-threaded REST API dispatcher & route handlers
│   └── static/                         # High-contrast Apple HIG client presentation layer
│       ├── app.js                      # Client state machine, Web Audio haptics, Chart.js bridges
│       ├── index.html                  # Unified dual-console single-page application
│       ├── login.html                  # Simplified credentials sign-in portal
│       └── styles.css                  # Tactile luxury styling, spring physics, specular lighting
├── tests/                              # Rigorous automated test suites (183 tests)
│   ├── test_api_connections.py         # Subsystem API health checks
│   ├── test_job_manager.py             # Vision job queue, timeouts, and persistence tests
│   ├── test_physics_signals_routing.py # Webster cycles, Greenshields physics, & routing tests
│   ├── test_prediction_pipeline.py     # Chronological date-split & feature vector tests
│   ├── test_synthesizer_hub.py         # Snapshot backup integrity, secret masking, & stream tests
│   └── test_vision_detector.py         # YOLO inference, empty frames, & zero vehicle tests
└── traffic_system/                     # Core computational and machine learning modules
    ├── artifacts/                      # Serialized models, encoders, and topology graphs
    ├── computer_vision/                # YOLO inference, ByteTrack tracking, incident detection
    ├── core/                           # Road registry, traffic physics, security & time utils
    ├── dispatch/                       # Central business logic and action recommendations
    ├── events/                         # Municipal event lifecycle and schedule matching
    ├── integrations/                   # External APIs (TomTom, Open-Meteo, Google Maps)
    ├── junction/                       # Junction telemetry and corridor monitor
    ├── live/                           # Real-time data bridge and API adapters
    ├── models/                         # ML inference, fallback strategies, and explainability
    ├── routing/                        # Graph pathfinding and dynamic detour calculations
    ├── simulation/                     # Greenshields macroscopic flow & Webster signal actuation
    ├── storage/                        # Video storage, migrations, and cleanup policies
    └── synthesizer/                    # System synthesizer & snapshot backup management
```

---

## Quickstart & Reproduction Guide

### 1. Prerequisites
* Python 3.10+ (tested on Python 3.11, 3.12, 3.14)
* pip package manager

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/Adhithya-kn/smart-traffic-ai.git
cd smart-traffic-ai

# (Optional) Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required pinned dependencies
pip install -r requirements.txt
```

### 3. Launching the System
To boot the multi-threaded server hosting both the Commuter Portal and Traffic Control Room:

```bash
python3 run_system.py 8080
```

Once running, navigate to:
* **Application URL**: `http://localhost:8080`
* **Road User Commuter Portal**: Log in as `commuter` (Password: `SecurePass@123`)
* **Traffic Authority Command Center**: Log in as `admin` (Password: `SecurePass@123`)

---

## Automated Test Suite & Verification

The system includes an extensive automated test suite covering unit invariants, cryptographic security, graph routing, computer vision, and physical simulation:

```bash
pytest -v
```

### Verified Test Results (180 Passed, 3 Skipped, 0 Failed, 0 Timed Out):
```
tests/test_api_connections.py .........                                  [  4%]
tests/test_api_integration_live.py sss                                   [  6%]
tests/test_api_security.py .......                                       [ 10%]
tests/test_architecture_solid_dry.py .....                               [ 13%]
tests/test_bengaluru_events_integration.py ....                          [ 15%]
tests/test_density.py ....                                               [ 17%]
tests/test_events_routing.py .                                           [ 18%]
tests/test_external_api_audit.py .........                               [ 22%]
tests/test_google_maps_integration.py ......                             [ 26%]
tests/test_health_readiness.py ....                                      [ 28%]
tests/test_incident_detector.py ....                                     [ 30%]
tests/test_job_manager.py .....                                          [ 33%]
tests/test_junction.py .                                                 [ 33%]
tests/test_live_simulation.py ......                                     [ 37%]
tests/test_models.py ...                                                 [ 38%]
tests/test_pcu_converter.py ....                                         [ 40%]
tests/test_persistence_lifecycle.py .......                              [ 44%]
tests/test_physics_signals_routing.py ................                   [ 53%]
tests/test_prediction_pipeline.py .......                                [ 57%]
tests/test_road_registry.py ...                                          [ 58%]
tests/test_run_system_and_deployment.py .........                        [ 63%]
tests/test_security_fast_cache.py ....                                   [ 66%]
tests/test_server_api.py .........                                       [ 71%]
tests/test_signin_portal_verification.py ...                             [ 72%]
tests/test_simulation.py ..                                              [ 73%]
tests/test_speed_estimator.py .....                                      [ 76%]
tests/test_synthesizer_hub.py ........                                   [ 80%]
tests/test_vehicle_counter.py ...                                        [ 82%]
tests/test_video_streaming_range.py ...                                  [ 84%]
tests/test_video_upload.py .......                                       [ 87%]
tests/test_vision_concurrency.py ...                                     [ 89%]
tests/test_vision_detector.py .....                                      [ 92%]
tests/test_vision_pipeline_robustness.py ......                          [ 95%]
tests/test_vision_security.py ........                                   [100%]

======================= 180 passed, 3 skipped in 20.61s ========================
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for complete details and third-party notices (including Ultralytics AGPL-3.0 and OpenCV Apache 2.0).

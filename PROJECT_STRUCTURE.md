# Project Architecture & Directory Structure Guide

> **Welcome to the Smart Traffic AI Project!**  
> This guide is written in plain, human, accessible English for beginners, junior developers, product managers, and non-technical teammates. It explains how the entire project is organized, what each file and folder does, and how all parts work together to predict and ease traffic congestion in smart cities.

---

## 1. The Big Picture: The "Smart City Traffic Command Center" Analogy

To understand this codebase without getting lost in technical jargon, imagine this project as a **real-world Smart City Traffic Operations Center** (like the traffic control room of Bengaluru or an airport operations tower).

Just like a modern municipal control center has dedicated staff, specialized equipment, and secure storage rooms, our software is split into 8 intuitive departments:

```
+==================================================================================================+
|                        SMART CITY TRAFFIC COMMAND CENTER (THE SYSTEM)                            |
+==================================================================================================+
|                                                                                                  |
|   1. THE EYES                        2. THE BRAIN                       3. THE SENSOR HUB        |
|   (traffic_system/computer_vision/)  (traffic_system/models/ & core/)   (traffic_system/live/)   |
|   - CCTV cameras & YOLO AI           - XGBoost congestion forecasting   - Live TomTom Traffic    |
|   - Vehicle detection & speeds       - 24 Bengaluru road corridors      - OpenWeather rain data  |
|   - Accident & stall detection       - Decision-tree root causes        - Google Maps API        |
|                                                                                                  |
|   4. THE CONTROL TOWER & SCREENS     5. THE SCENARIO LAB                6. THE MEMORY VAULT      |
|   (app/ & api/)                      (traffic_system/simulation/)       (traffic_system/storage/)|
|   - Commuter navigation portal       - "What-if" policy testing         - Trained model files    |
|   - Traffic Authority command room   - Smart green-light timing         - SQLite database & jobs |
|   - Tactile dark-mode dashboard      - Greenshields traffic physics     - Road network maps      |
|                                                                                                  |
|   7. THE SAFETY SHIELD               8. THE TOOL SHED                                            |
|   (tests/)                           (scripts/)                                                  |
|   - 212 automated safety checks      - Terminal pipeline demonstrator                            |
|   - Prevents bugs & regressions      - Real video processing scripts                             |
|   - Verifies math & security         - Static asset synchronizer                                 |
|                                                                                                  |
+==================================================================================================+
```

---

### Detailed Department Breakdown

### 1. 👁️ The Eyes — CCTV & Computer Vision (`traffic_system/computer_vision/`)
* **What it represents**: Overhead traffic cameras mounted along expressways and intersections.
* **What it does**:
  * Scans video footage frame-by-frame using **YOLO** (You Only Look Once) neural networks to spot cars, motorcycles, auto-rickshaws, buses, and trucks.
  * Tracks vehicles across frames using **ByteTrack** so the same car isn't counted twice.
  * Calculates real-world speeds in km/h from camera pixels using homography transforms.
  * Converts mixed traffic into standard **Passenger Car Units (PCU)**.
  * Immediately flags stopped vehicles, accidents, or sudden brake shockwaves.

### 2. 🧠 The Brain — AI & Spatio-Temporal Prediction (`traffic_system/models/` & `traffic_system/core/`)
* **What it represents**: Senior traffic data scientists analyzing citywide congestion patterns.
* **What it does**:
  * Understands the connected road map of **24 major Bengaluru corridors** (like Outer Ring Road, Silk Board, Indiranagar, and Hebbal).
  * Takes current vehicle counts, travel speeds, time of day, and day of week, and predicts traffic jams **30 to 60 minutes before they occur**.
  * Uses **XGBoost gradient boosting** models trained on tens of thousands of historical records.
  * Doesn't just give a prediction—it explains **why** traffic is slow (for example: *"42% due to road bottleneck, 36% due to evening rush hour"*) using transparent decision-tree path attribution.

### 3. 📡 The Sensor Hub — Live Integrations (`traffic_system/integrations/` & `traffic_system/live/`)
* **What it represents**: External weather stations, radio alerts, and regional traffic feeds.
* **What it does**:
  * Connects to external web services like **TomTom Traffic** to pull real-time ground-truth traffic speeds.
  * Connects to weather APIs (**Open-Meteo / OpenWeatherMap**) to see if monsoon downpours or fog will slow down traffic.
  * Checks **Google Maps Distance Matrix** for cross-validation when available.
  * Gracefully switches to historical fallbacks if an external internet service goes down or runs out of quota.

### 4. 🖥️ The Control Tower & Display Screens — Web Dashboard (`app/` and `api/`)
* **What it represents**: The physical control room displays, computer monitors, and mobile apps.
* **What it does**:
  * Serves a responsive web application built with an Obsidian luxury dark-mode aesthetic.
  * Provides two distinct experiences:
    1. **The Commuter Portal**: Drivers can select departure times, view expected congestion levels, see the root cause, and receive **smart detour routes with estimated minutes saved**.
    2. **The Municipal Authority Room**: City engineers view an 8-zone heat map, inject road closures or construction permits, test traffic signal adjustments, and review CCTV alerts.
  * Powers the backend REST API (`app/server.py`) and cloud serverless gateway (`api/index.py`).

### 5. 🔬 The Scenario Lab — Simulation & Signal Optimization (`traffic_system/simulation/`)
* **What it represents**: A sandbox environment where engineers test traffic policies before rolling them out onto actual roads.
* **What it does**:
  * Uses **Greenshields Macroscopic Fluid Physics** to simulate what happens if 15% of drivers take alternate routes.
  * Uses **Webster's Signal Timing Formula** to calculate delay-minimizing green-light and red-light cycle times (e.g., giving 55 seconds to North-South and 35 seconds to East-West).
  * Strictly operates as an **Advisory & Decision-Support System**—it provides recommendations for human traffic operators, rather than directly rewiring physical street lights.

### 6. 🗄️ The Memory Vault — Storage & Artifacts (`traffic_system/storage/` & `traffic_system/artifacts/`)
* **What it represents**: The secure records archive and file repository.
* **What it does**:
  * Stores trained machine learning model files (`xgboost_model.joblib`), pure-Python fast-inference tree weights (`model_trees.json`), and road network maps (`network_topology.json`).
  * Stores municipal roadwork permits (`events.json`) and salted user credentials (`users.json`).
  * Manages uploaded traffic video files in `traffic_system/storage/videos/`, using atomic file operations so files are never corrupted if the power cuts out.

### 7. 🛡️ The Safety Shield — Test Suite (`tests/`)
* **What it represents**: The quality assurance team and safety building inspectors.
* **What it does**:
  * Runs **212 automated tests** across 37 test modules before any new feature is approved.
  * Tests everything: mathematical formulas, security authentication, API response formats, camera vehicle counters, and deployment configurations.
  * Ensures a change made in one corner of the project never accidentally breaks something else.

### 8. 🧰 The Tool Shed — Utility Scripts (`scripts/`)
* **What it represents**: Handy power tools and diagnostic gadgets for engineers.
* **What it does**:
  * **`demonstrate_pipeline.py`**: A 13-stage interactive command-line walkthrough demonstrating the entire pipeline from raw data to prediction and detour advice.
  * **`demonstrate_bengaluru_video.py`**: A quick tool to run YOLO object detection and vehicle counting on real CCTV video clips.
  * **`sync_static.py`**: Keeps frontend static web assets perfectly mirrored across deployment directories.

---

## 2. Complete Directory Map

Below is a bird's-eye view of every important directory and file in the project, explaining its exact purpose in one clear sentence:

| Folder / File Path | Command Center Role | Plain-English Description |
| :--- | :--- | :--- |
| **`app/`** | Control Tower | The web application containing the backend HTTP server (`server.py`) and user interfaces. |
| **`app/static/`** | Display Screens | Frontend HTML, CSS, JavaScript, and sample demo videos seen by users in their browser. |
| **`app/routes/`** | Switchboard | Specialized API routes (e.g., `vision_routes.py` for handling chunked video uploads). |
| **`api/`** | Cloud Gateway | Serverless entrypoint (`api/index.py`) connecting Vercel cloud deployments to our server. |
| **`architecture/`** | Blueprints | Master architecture diagrams (`.png`, `.svg`), visual HTML flowcharts, and research guides. |
| **`Dataset/`** | Historical Archive | Benchmark traffic dataset (`Banglore_traffic_Dataset.csv`) with 57,600+ telemetry rows across Bengaluru. |
| **`Literature/`** | Academic Library | Curated transportation science research papers and mathematical reference documents. |
| **`scripts/`** | Tool Shed | Executable utilities for 13-stage pipeline demonstrations, video tests, and asset sync. |
| **`tests/`** | Safety Shield | Over 212 automated test cases verifying math, machine learning, vision, and security. |
| **`traffic_system/`** | The Brain & Engine | The core Python package containing all AI models, computer vision, physics, and routing logic. |
| **`traffic_system/artifacts/`** | Memory Vault | Trained machine learning model weights, encoders, road topology, and active road events. |
| **`traffic_system/computer_vision/`**| The Eyes | YOLO vehicle detection, ByteTrack tracking, speed estimation, and accident detection. |
| **`traffic_system/core/`** | Fundamentals | Road registry, physical constants (Level of Service, SPI), and cryptographic security utils. |
| **`traffic_system/dispatch/`** | Tactical Dispatch | Central coordinator that ties predictions, events, and signal recommendations together. |
| **`traffic_system/events/`** | Incident Log | Manages real-time roadworks, sports stadium crowds, and water pipeline trenching permits. |
| **`traffic_system/integrations/`**| Sensor Hub | Clients connecting to TomTom Traffic, OpenWeatherMap, and Google Maps APIs. |
| **`traffic_system/junction/`** | Intersection Monitor | Telemetry aggregator and queue length estimator for specific road junctions. |
| **`traffic_system/live/`** | Real-Time Bridge | Ingests live telemetry streams with automatic fallback to historical patterns. |
| **`traffic_system/models/`** | Prediction Models | XGBoost multi-class classifier and decision-tree path feature attribution engine. |
| **`traffic_system/routing/`** | GPS Navigator | Dynamic Dijkstra pathfinding that routes commuters around traffic jams using roadwork penalties. |
| **`traffic_system/simulation/`** | Scenario Lab | Greenshields hydrodynamic flow simulation and Webster delay-minimizing signal timing. |
| **`traffic_system/storage/`** | File Locker | Video storage manager handling chunked uploads and atomic disk writes. |
| **`traffic_system/synthesizer/`**| Stress Tester | Generates synthetic telemetry for testing and handles encrypted snapshot backups. |
| **`run_system.py`** | Ignition Key | The main command-line entrypoint used to validate the environment and launch the web server. |
| **`requirements.txt`** | Supply List | Pinned list of exact Python library versions required to run the project. |
| **`PROJECT_STRUCTURE.md`** | You Are Here! | This beginner-friendly, accessible architecture and directory guide. |
| **`README.md`** | Master Technical Doc | Comprehensive technical reference manual, operational invariants, and research benchmarks. |
| **`PROJECT.md`** | Milestone Roadmap | Project execution milestones, interface contracts, and task progress tracker. |
| **`render.yaml` & `Procfile`**| Cloud Blueprint | Production deployment configurations for hosting on Render with persistent disk storage. |
| **`vercel.json`** | Serverless Config | Routing rules and memory execution limits for hosting on Vercel. |
| **`LICENSE`** | Legal Permissions | Open-source MIT license and third-party notices (Ultralytics AGPL-3.0, OpenCV, XGBoost). |

---

## 3. How to Run the Project Safely in 3 Steps

Running this project does not require an advanced degree in computer science. Follow these three simple steps:

### Step 1: Install Python Dependencies
Open your computer's terminal (or command prompt), navigate to the project directory, and install the required libraries:

```bash
# Navigate to the project root
cd /Users/ak/Documents/Dp-01

# (Recommended) Activate your Python virtual environment if you use one:
# source venv/bin/activate

# Install the exact pinned dependencies
pip install -r requirements.txt
```

### Step 2: Launch on a Safe Port
> ⚠️ **CRITICAL PORT SAFETY NOTICE**:  
> In shared or development environments, common ports like `8080` (often used by Apache Tomcat) or `8081` (often used by other background web services) may already be occupied by external applications.  
> **Never kill or interrupt existing system processes!**  
> Instead, launch our application on a **safe, free port** such as `8089` (or `8090`):

```bash
# Option A: Pass the safe port directly as a command-line argument:
python3 run_system.py 8089

# Option B: Or set the PORT environment variable:
PORT=8089 python3 run_system.py
```

When it starts successfully, you will see pre-flight diagnostics confirming that all models, road topologies, and routes are validated and ready:
```
============================================================
 SMART TRAFFIC AI: SPATIO-TEMPORAL MONITORING & CONTROL ROOM
============================================================
[PRE-FLIGHT] Model files verified: OK
[PRE-FLIGHT] Road network topology verified: OK
[HTTP] Server listening on http://0.0.0.0:8089
[READY] Press Ctrl+C to gracefully stop the server.
```

### Step 3: Open in Your Web Browser
Open your favorite browser (Chrome, Safari, Firefox, or Edge) and go to:
* **Web Address**: `http://localhost:8089`

You can sign in using either of the built-in demo profiles:
* **Everyday Commuter Profile**:
  * Username: `commuter`
  * Password: `SecurePass@123`
  * *Features*: Explore trip departure times, view predicted congestion risk, see plain-English explanations, and find detours that save travel time.
* **Traffic Authority Operator Profile**:
  * Username: `admin`
  * Password: `SecurePass@123`
  * *Features*: Monitor the 8-zone city heatmap, add/remove roadwork events, simulate green-light timings, and upload CCTV traffic videos for AI analysis.

---

### Helpful Quick Commands

* **Run the 13-Stage Terminal Walkthrough**:
  ```bash
  python3 scripts/demonstrate_pipeline.py
  ```
  *Prints a complete step-by-step demonstration of the AI models, graph routing, and signal calculations in your terminal.*

* **Run the Automated Safety Shield (Test Suite)**:
  ```bash
  pytest -m "not integration"
  ```
  *Runs all 212 automated unit tests in under 45 seconds to verify that everything is working properly.*

---

## 4. Glossary of Common Traffic AI Terms

When reading the code or talking with teammates, you will frequently hear these terms. Here is what they mean in simple everyday language:

| Term | What It Stands For | Plain-English Definition |
| :--- | :--- | :--- |
| **YOLO** | You Only Look Once | A state-of-the-art computer vision neural network that detects objects (cars, buses, pedestrians) in an entire video image in a single millisecond pass. |
| **ByteTrack** | Byte Tracking Algorithm | An algorithm that follows detected vehicles from frame to frame as they drive down a road, assigning each vehicle a unique ID so it isn't counted twice. |
| **PCU** | Passenger Car Unit | A standard transportation metric that converts different vehicle types into equivalent cars (e.g., 1 motorcycle = 0.5 PCU, 1 city bus = 3.0 PCUs) so traffic volume can be measured fairly. |
| **Level of Service (LoS)** | Highway Level of Service | A standard letter grade from **A** (free-flowing traffic, fast speeds) to **F** (gridlock breakdown, bumper-to-bumper standstill). |
| **Congestion Index / SPI** | Standard Performance Index | A numerical score between 0.0 (empty road) and 1.0 (complete jam) summarizing the severity of traffic delay on a corridor. |
| **BPR Curve** | Bureau of Public Roads Formula | A classical transportation physics formula that calculates how travel time climbs exponentially as the number of cars approaches the road's maximum capacity. |
| **Greenshields Model** | Greenshields Flow Physics | A foundational traffic engineering equation ($q = k \cdot v$) stating that traffic flow equals vehicle density times travel speed. |
| **Webster's Formula** | Webster Minimum-Delay Formula | A mathematical equation used by city planners to calculate the optimal green and red light timing for traffic signals to minimize overall vehicle waiting time. |
| **Tree-Path Attribution** | Decision Tree Path Analysis | A transparent way to explain AI predictions by tracing which specific rules in the decision trees led to the final congestion alert. |
| **REST API** | Representational State Transfer | A standard way for web browsers and mobile apps to ask the backend server for information (like *"GET /api/corridors/all"* or *"POST /api/route/evaluate"*). |
| **SSE** | Server-Sent Events | A lightweight web technology that lets the server push real-time traffic alerts and camera updates to the browser instantly without the user having to refresh the page. |
| **Shannon Entropy** | Information Entropy Gate | A mathematical check ($H(p)$) that measures how confident the AI is in its prediction; if the model is uncertain, it alerts operators rather than guessing wildly. |
| **Atomic File Operations** | Two-Phase POSIX Writes | A data safety technique where new files are written to a temporary name first and then renamed in a single unbreakable step, preventing data corruption if a power loss occurs. |
| **Advisory Mode** | Decision-Support System | Means our system provides smart recommendations and guidance to human traffic operators, but does not autonomously switch physical high-voltage street lights. |

---

## 5. Summary & Getting Help

* For deep mathematical formulations, research literature citations, and API endpoint schemas, consult **`README.md`** and **`architecture/SYSTEM_ARCHITECTURE_AND_FLOW.md`**.
* For milestone progress and interface contracts, consult **`PROJECT.md`**.
* If you have questions or discover unexpected behavior, run the automated test suite (`pytest -m "not integration"`) to pinpoint which module is affected.

*Happy navigating and smart driving!*

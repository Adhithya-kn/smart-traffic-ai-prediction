# System Architecture Analysis & Component Topologies

**Author:** Senior Machine Learning & Pipeline Architect  
**Reviewer:** Principal System Orchestrator  

---

## 1. Architectural Philosophy & Layered Decomposition

The system is engineered as an **integrated multi-tier pipeline** designed with clean separation of concerns and zero circular dependencies:

```
+------------------------------------------------------------------------------------+
|                                    PRESENTATION LAYER                              |
|   - Obsidian Dark Glass Command Dashboard                                          |
|   - Real-Time KPI Tickers (Active Segments, Severe Breakdown Rate, Mitigation %)   |
|   - Interactive Counterfactual Simulation Controls (Demand Alpha & Speed Beta)     |
|   - Spatial Corridor Congestion Distribution & Drill-Down Views                     |
+------------------------------------------------------------------------------------+
                                          ^
                                          | JSON State / Data Payloads
                                          v
+------------------------------------------------------------------------------------+
|                             DECISION & DISPATCH LAYER                              |
|   - Prescriptive Operational Directives Dispatcher                                 |
|   - Severe / High / Moderate Action Taxonomy                                       |
|   - Municipal Notification & Signal Coordination Formatter                         |
+------------------------------------------------------------------------------------+
                                          ^
                                          | Simulated & Predicted Outcomes
                                          v
+------------------------------------------------------------------------------------+
|                             SIMULATION & MITIGATION LAYER                          |
|   - Counterfactual Perturbation Core (Demand Elasticity & Speed Restoration)       |
|   - Multi-Feature Scenario Transformation Vector                                  |
|   - Before vs After Transition Impact Matrix Calculator                            |
+------------------------------------------------------------------------------------+
                                          ^
                                          | Feature Matrix & Predictor
                                          v
+------------------------------------------------------------------------------------+
|                             PREDICTIVE MODELING LAYER                              |
|   - Preprocessing ColumnTransformer (Median Imputer + OneHotEncoder)               |
|   - XGBClassifier Multi-Class Softmax Engine                                       |
|   - Evaluation Metrics Core (Accuracy, Precision, Recall, F1, Confusion Matrix)    |
|   - Model Persistence & Artifact Serialization (joblib)                            |
+------------------------------------------------------------------------------------+
                                          ^
                                          | Cleaned Features & Temporal Horizons
                                          v
+------------------------------------------------------------------------------------+
|                           INGESTION & DATA INTEGRITY LAYER                         |
|   - Raw CSV Telemetry Stream Ingestion (203k+ Records)                             |
|   - Deduplication & Primary Key Integrity Check (`record_id`)                      |
|   - Temporal ISO Datetime Normalization & Chronological Ordering                   |
|   - Forward Shift-Based Target Synthesis (`Future_Congestion` by `road_id`)       |
+------------------------------------------------------------------------------------+
```

---

## 2. Invariant Boundary Rules

1. **Rule 1 (Zero Model Leakage into Ingestion):** The Ingestion Layer must have zero dependencies on machine learning libraries (`xgboost`, `sklearn`). It outputs pure, structured pandas DataFrames.
2. **Rule 2 (Deterministic Simulation Coupling):** The Simulation Layer does NOT train models. It re-uses the frozen, serialized model pipeline produced by the Predictive Modeling Layer to score counterfactual states.
3. **Rule 3 (Presentation Independence):** The presentation layer interacts solely with structured outputs; no raw machine learning pipeline code may be embedded directly in UI markup.

---

## 3. Dual-Persona Operational Architecture

```
                                    APP SERVER & DISPATCHER
                                               |
         +-------------------------------------+-------------------------------------+
         |                                                                           |
         v                                                                           v
+-----------------------------------------------+       +-----------------------------------------------+
|      PERSONA 1: COMMUTER SMART NAVIGATOR      |       |  PERSONA 2: TRAFFIC AUTHORITY CONTROL ROOM    |
+-----------------------------------------------+       +-----------------------------------------------+
| - Account Login / Secure Registration         |       | - Role-Based Access Control (Admin / Operator)|
| - Origin & Destination Corridor Selection     |       | - Metropolitan Multi-Zone Overview (6 Zones)  |
| - Calendar Date & Time Schedule Picker        |       | - Dynamic Event Injector & Broadcaster        |
| - Real-Time Municipal Event Overlay           |       | - Proactive Counterfactual Policy Simulator   |
| - XGBoost 4-State Congestion Prediction       |       |   (Demand Alpha 0-50%, Speed Beta 0-30%)      |
| - Intelligent Event-Aware Altered Reroute     |       | - Automated Municipal Action Dispatcher       |
|   (Bypasses bottleneck, calculates time saved)|       |   (Signal Phase Extensions, VMS Alerts)       |
+-----------------------------------------------+       +-----------------------------------------------+
```

### 3.1 Event-Aware Route Alteration Flow
1. **Schedule Formulation:** Commuter selects travel corridor, target date, and departure time.
2. **Event Intersection:** The `EventManager` queries all active events (stadium games, festivals, weather, road closures) intersecting the primary corridor.
3. **Forward Horizon Scoring:** The `TrafficPredictor` scores segments into `Low`, `Moderate`, `High`, or `Severe`.
4. **Altered Route Discovery:** If primary path is `Severe` or `High` (or blocked by an active event), the `RouteNavigator` identifies adjacent bypass corridors in the zone with `Low`/`Moderate` predicted congestion.
5. **Human Narrative Delivery:** Computes estimated travel time saved (e.g. 25.0 minutes) and delivers actionable explanation.

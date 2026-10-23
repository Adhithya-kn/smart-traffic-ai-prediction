# Requirements Register: Smart Traffic AI System

**Status:** APPROVED by Senior Domain Architect  
**Traced Scope:** 30 Functional Requirements (FR), 10 Non-Functional Requirements (NFR), 5 Invariant Constraints (CON)  

---

## 1. Functional Requirements (FR)

### Module 1: Ingestion & Telemetry Data Integrity
- **FR-001 [D, S]:** The system must ingest high-volume spatio-temporal telemetry (≥200,000 records) from CSV format containing 12 primary telemetry attributes.
- **FR-002 [S]:** The ingestion pipeline must remove duplicate records identified by unique `record_id`.
- **FR-003 [S]:** The system must purge observations missing essential fields (`timestamp`, `road_id`, `congestion_level`, `vehicle_count`, `average_speed`).
- **FR-004 [S]:** Timestamps must be standardized to ISO datetime format and sorted chronologically to prevent temporal look-ahead leakage.
- **FR-005 [D]:** The telemetry ingestor must validate network entities across 94 roads (`RD_100`–`RD_193`), 100 intersections (`INT_001`–`INT_100`), and 6 city zones.

### Module 2: Spatio-Temporal Feature Engineering
- **FR-006 [S]:** The pipeline must compute the forward horizon target $\text{Future\_Congestion}_{t} = \text{Congestion\_Level}_{t+1}$ partitioned by `road_id`.
- **FR-007 [S]:** The preprocessor must isolate numerical features and apply median imputation to handle sensor dropouts.
- **FR-008 [S]:** Categorical identifiers (`city_zone`, `road_id`, `intersection_id`) must be transformed using One-Hot Encoding within a scikit-learn `ColumnTransformer`.
- **FR-009 [L]:** The feature extractor must generate temporal indicators: `hour`, `day_of_week`, `is_weekend`, `is_holiday`, `rush_hour`, and `peak_period`.
- **FR-010 [L]:** Exogenous meteorological inputs (`temperature`, `rainfall`, `weather_condition`) must be coupled with traffic flow rates.

### Module 3: Gradient-Boosted Predictive Ensemble
- **FR-011 [S]:** The predictive core must train an `XGBClassifier` to forecast multi-class congestion states: `Low`, `Moderate`, `High`, and `Severe`.
- **FR-012 [S]:** The model must output discrete class predictions and calibrated probability distributions for all network segments.
- **FR-013 [S]:** The evaluation engine must report multi-class Accuracy, Weighted Precision, Weighted Recall, and Weighted F1-Score.
- **FR-014 [S]:** A confusion matrix must be generated and rendered to inspect misclassifications between adjacent congestion tiers.
- **FR-015 [D, V]:** The trained model must sustain a prediction match rate of ≥90% on the baseline dataset.

### Module 4: Counterfactual Policy Simulation Core
- **FR-016 [S]:** The simulation core must accept dynamic policy adjustment parameters: demand reduction factor $\alpha$ (default 20%) and speed recovery factor $\beta$ (default 10%).
- **FR-017 [S]:** The simulator must adjust flow variables (`vehicle_count`, `heavy_vehicle_count`, `motorcycle_count`, `traffic_density`, `queue_length`, `average_wait_time`, `traffic_flow_rate`) by factor $(1 - \alpha)$.
- **FR-018 [S]:** The simulator must adjust vehicle speed by $(1 + \beta)$, capped at road speed limit.
- **FR-019 [S]:** The simulation engine must execute model inference on perturbed feature vectors to produce `Simulated_Congestion_After_Action`.
- **FR-020 [S, V]:** The simulator must calculate the net transition impact matrix (de-escalated, unchanged, worsened segments).

### Module 5: Prescriptive Operational Decision Dispatch
- **FR-021 [S]:** The decision engine must automatically assign actionable municipal recommendations based on predicted severity.
- **FR-022 [S]:** Segments predicted as `Severe` must trigger priority incident investigations, dynamic signal coordination, alternative route diversions, and transit priority.
- **FR-023 [S]:** Segments predicted as `High` must trigger signal timing review, peak-hour demand management, and alternate arterial alerts.
- **FR-024 [S]:** Segments predicted as `Moderate` must trigger corridor monitoring and signal offset micro-tuning.
- **FR-025 [S]:** Segments predicted as `Low` must maintain baseline traffic monitoring.

### Module 6: Command Center Visual Interface
- **FR-026 [A]:** The system must present an interactive command dashboard with real-time KPI tickers (Active Roads, Critical Congestion %, De-escalation Rate).
- **FR-027 [A]:** The UI must support interactive zone and road corridor filtering across all 6 zones.
- **FR-028 [A]:** An interactive counterfactual slider must allow city operators to test arbitrary $\alpha$ and $\beta$ mitigation policies in real-time.
- **FR-029 [A]:** A spatial corridor heatmap or network graph must illustrate congestion hotspots.
- **FR-030 [A]:** Detailed tabular views must permit drill-down by `record_id` with side-by-side Before/After comparison.

---

## 2. Non-Functional Requirements (NFR)

- **NFR-001 (Inference Latency):** Batch model inference for 10,000 road segments must execute in < 250 milliseconds.
- **NFR-002 (Throughput):** Full pipeline ingestion and scoring of 200,000 records must complete within < 15 seconds.
- **NFR-003 (Deterministic Reproducibility):** Pipeline runs with identical random seed must produce bit-for-bit identical predictions and metrics.
- **NFR-004 (Modular Decoupling):** Zero cross-layer contamination; data ingestion, ML pipelines, simulation math, and UI layers must reside in distinct packages.
- **NFR-005 (Aesthetic Luxury):** UI must use Apple HIG standards, obsidian dark palette (`#07080a`), frosted glass, and responsive typography.

# Problem Statement: Smart Traffic Monitoring & Proactive Congestion Prediction

**Status:** APPROVED by Senior Domain Architect  
**Author:** Senior Requirements & Domain Architect  

---

## 1. Context & Motivation

Metropolitan areas globally are experiencing unprecedented growth in vehicle density, leading to recurring congestion bottlenecks. In addition to compounding commuter stress and economic losses, congestion accounts for over 25% of urban greenhouse gas emissions and causes disproportionate wear on road infrastructure.

Traditional municipal traffic management relies predominantly on **reactive architectures**:
1. **Isolated Static Timers:** Traffic lights cycle through pre-programmed green/red durations based on historical averages, unable to react to sudden surges or incidents.
2. **Lagged Sensor Reporting:** Loop detectors and camera feeds report congestion *after* vehicles have already accumulated into queues, leaving operators unable to prevent shockwaves.
3. **Passive Consumer Navigation Apps:** Consumer navigation apps (Google Maps, Apple Maps, Waze) reroute individual drivers without coordinating network-wide flow, often dumping thousands of vehicles onto narrow suburban arterials and creating secondary gridlocks.

---

## 2. The Core Problem Statement

> **How can an Intelligent Transportation System simultaneously monitor high-frequency multi-zone telemetry, accurately predict forward-horizon congestion states across dense road-intersection topologies, and simulate counterfactual mitigation interventions to dispatch actionable operational directives before breakdown occurs?**

---

## 3. Root Cause Analysis

```
                                  CONGESTION BREAKDOWN
                                           |
         +---------------------------------+---------------------------------+
         |                                 |                                 |
         v                                 v                                 v
[Root Cause 1: Latency]           [Root Cause 2: Open-Loop]         [Root Cause 3: Fragmentation]
Monitoring systems report         Standard ML models predict        Traffic control (signals)
what happened 15 minutes ago;     congestion without evaluating      operates separately from
traffic shockwaves travel at      how policy interventions          predictive models and
15–20 km/h upstream.              would de-escalate it.             environmental telemetry.
```

---

## 4. System Objectives

1. **High-Resolution Monitoring:** Ingest and normalize telemetry across 94 roads and 100 intersections spanning 6 distinct functional urban zones (`Downtown Core`, `Financial District`, `Suburban North`, `Tech Park`, `Residential West`, `Industrial East`).
2. **Predictive Horizon Modeling:** Formulate and train a high-accuracy, multi-class gradient boosted model (`XGBoost`) capable of forecasting transitions to `Low`, `Moderate`, `High`, or `Severe` congestion.
3. **Counterfactual Policy Simulation:** Provide a mathematically grounded simulation engine that evaluates the impact of traffic diversion ($\alpha$) and signal speed gains ($\beta$).
4. **Prescriptive Action Automation:** Eliminate cognitive overload for municipal operators by automatically mapping predicted risk levels to verified intervention directives.

---

## 5. Explicit Assumption Ledger

| ID | Assumption | Scope / Impact | Status |
| :---: | :--- | :--- | :---: |
| **A-001** | The sequential records grouped by `road_id` represent consecutive observation intervals suitable for shift-based horizon forecasting. | ML feature engineering | Verified `[D, S]` |
| **A-002** | The 6 city zones represent distinct functional urban archetypes with varying peak-hour and diurnal demand profiles. | Ingestion & UI | Verified `[D]` |
| **A-003** | A dynamic traffic rerouting campaign can realistically achieve up to a 20% vehicle demand reduction on congested segments ($\alpha=0.20$). | Simulation physics | Grounded `[L, S]` |
| **A-004** | Coordinated green-wave signal retiming can yield up to a 10% average travel speed improvement ($\beta=0.10$). | Simulation physics | Grounded `[L, S]` |
| **A-005** | Roadway segments operate within physical speed limits, and simulation gains cannot exceed posted limits. | Capacity constraint | Bound `[A]` |

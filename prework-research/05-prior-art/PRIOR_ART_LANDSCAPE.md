# Prior Art Landscape: Comparative Matrix

**Lead Author:** Junior Literature Researcher  
**Supervising Reviewer:** Senior Requirements & Domain Architect  

---

## 1. Competitive & Academic Landscape

We benchmark our system against existing commercial, open-source, and academic archetypes:

1. **Consumer Navigation Systems (Google Maps, Apple Maps, Waze):**
   - *Strengths:* Excellent real-time GPS probe coverage, live routing for individual drivers.
   - *Weaknesses:* Selfish individual routing creates secondary suburban bottlenecks; closed source; zero municipal signal integration; no counterfactual "what-if" policy testing.
2. **Municipal SCATS / SCOOT Systems:**
   - *Strengths:* Direct physical actuation of traffic signals via inductive loops.
   - *Weaknesses:* Rigid localized loop controllers; purely reactive; blind to upcoming multi-zone shockwaves; exorbitant hardware deployment costs.
3. **Academic Deep Learning Models (ST-GCN, DCRNN, ASTGCN):**
   - *Strengths:* High theoretical predictive accuracy on benchmark datasets (METR-LA, PeMS-Bay).
   - *Weaknesses:* Extremely high inference latency; uninterpretable black boxes; requires heavy GPU infrastructure; purely passive forecasting without intervention simulation.
4. **Our System (AI-Based Smart Traffic Monitoring & Congestion Prediction System):**
   - *Advantage:* Blends high-efficiency, multi-class gradient boosting with an active counterfactual simulation engine and automated municipal dispatch.

---

## 2. Comparative Feature Matrix

| Feature / Dimension | Google Maps / Waze | Municipal SCATS/SCOOT | Academic GNN Papers | **Our System** |
| :--- | :---: | :---: | :---: | :---: |
| **Real-Time Multi-Zone Telemetry** | High | Low (Localized) | Medium (Offline) | **High (203k+ records)** |
| **Heterogeneous Vehicle Modeling** | No | No | Rare | **Yes (Trucks, Bikes, Buses)** |
| **Weather & Environmental Inputs** | Rare | No | Sometimes | **Yes (Rain, Temp, Conditions)** |
| **Forward Horizon Prediction** | Real-time / Short | Reactive Only | Predictive (Offline) | **Predictive (XGBoost Multi-Class)** |
| **Counterfactual Policy Simulation**| **NO** | **NO** | **NO** | **YES (Demand & Speed Vectors)** |
| **Automated Municipal Action Dispatch** | No | Rule-Based | No | **YES (4-Tier Action Engine)** |
| **Human-Crafted Obsidian Dashboard**| Proprietary | Archaic 1990s UI | Matplotlib Plots | **YES (Modern Luxury Dark Glass)** |
| **Compute & Inference Footprint** | Massive Cloud | Specialized HW | GPU Servers | **Lightweight CPU/Web Capable** |

# Alternatives & Trade-Off Analysis

**Lead Author:** Senior Machine Learning & Pipeline Architect  
**Reviewer:** Principal System Orchestrator  

---

## 1. Predictive Model Paradigm: XGBoost vs Deep Learning GNN

| Evaluation Criteria | Deep Learning (ST-GCN / DCRNN) | Ensemble Trees (XGBoost) | Verdict & Rationale |
| :--- | :--- | :--- | :--- |
| **Tabular Sensor Heterogeneity** | Poor to moderate; sensitive to unscaled and missing values. | **Superior;** handles mixed discrete and continuous features effortlessly. | **WINNER: XGBoost** |
| **Inference Latency** | High (> 150ms per batch); requires GPU acceleration. | **Sub-millisecond (< 15ms per batch)** on standard CPUs. | **WINNER: XGBoost** |
| **Missing Value Robustness** | Fails unless complex neural imputation layers are added. | **Native branch imputation** for missing features. | **WINNER: XGBoost** |
| **Memory & Serialization** | Heavyweight checkpoints (> 300 MB). | Lightweight serialized artifacts (< 15 MB). | **WINNER: XGBoost** |
| **Academic Viva Explainability** | Hard to defend in real-time viva (black box). | **High interpretability** via feature importances and tree splits. | **WINNER: XGBoost** |

---

## 2. Target Formulation: Classification vs Continuous Regression

- **Option A (Continuous Speed/Flow Regression):** Predicts numerical speed ($v_{t+1}$).
  - *Drawback:* Difficult to translate directly into municipal operational alerts; errors of $\pm 5$ km/h can oscillate across arbitrary boundary thresholds.
- **Option B (Multi-Class Congestion Categorization - SELECTED):** Directly predicts Level of Service tiers (`Low`, `Moderate`, `High`, `Severe`).
  - *Advantage:* Directly aligns with Highway Capacity Manual standards and enables unambiguous 1-to-1 mapping into operational action directives.

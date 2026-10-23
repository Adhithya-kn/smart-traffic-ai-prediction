# Architecture Decision Records (ADRs)

---

## ADR-001: Selection of XGBoost as Core Predictive Engine
- **Status:** APPROVED
- **Date:** 2026-10-22
- **Context:** System requires high-accuracy multi-class horizon forecasting across 200k+ tabular records with low latency.
- **Decision:** Use `xgboost.XGBClassifier` with `ColumnTransformer` (median imputation + OneHotEncoding).
- **Consequences:** Sub-millisecond CPU inference, robust missing value handling, easy viva explainability.

---

## ADR-002: Shift-Based Road-Grouped Horizon Formulation
- **Status:** APPROVED
- **Date:** 2026-10-22
- **Context:** Need forward-looking predictive capability without temporal look-ahead leakage.
- **Decision:** Synthesize target using `df.groupby("road_id")["congestion_level"].shift(-1)`.
- **Consequences:** Eliminates temporal leakage across different physical roads; the last observation of each corridor is safely dropped.

---

## ADR-003: Linear Counterfactual Intervention Vector ($\alpha=0.20, \beta=0.10$)
- **Status:** APPROVED
- **Date:** 2026-10-22
- **Context:** Need a grounded simulation mechanism to model proactive mitigation before gridlock occurs.
- **Decision:** Apply a 20% demand reduction factor to flow variables and a 10% speed gain to average speeds, bounded by speed limits.
- **Consequences:** Provides grounded civil engineering realism; yields 5,949 de-escalated road segments on the baseline dataset.

---

## ADR-004: Obsidian Dark Luxury Aesthetic Standard for UI
- **Status:** APPROVED
- **Date:** 2026-10-22
- **Context:** Strict anti-AI slop mandate requiring human-crafted, tactile interface.
- **Decision:** Mandate obsidian `#07080a` background, Apple HIG frosted glass cards, translucent borders, and spring physics.
- **Consequences:** High visual distinction, superior usability for municipal control rooms, distinct from generic template generators.

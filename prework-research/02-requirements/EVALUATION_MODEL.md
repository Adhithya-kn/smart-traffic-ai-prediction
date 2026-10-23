# Evaluation Model & Capstone Grading Rubric

**Context:** B.Tech Design Project / Capstone Engineering Evaluation  
**Assessment Target:** 100 Marks Breakdown (Architecture, Methodology, Model, Simulation, UI, Viva)  

---

## 1. 100-Mark Allocation Matrix

| Module / Evaluation Dimension | Weight | Target Artifacts | Implicit Grader Expectations |
| :--- | :---: | :--- | :--- |
| **1. Domain Research & Literature** | **15 Marks** | `prework-research/03-domain/`, `05-prior-art/`, 10 cited papers | Proves deep theoretical grounding in MFD, speed-density dynamics, and spatio-temporal modeling. No shallow Wikipedia definitions. |
| **2. Requirements & Architecture** | **15 Marks** | `02-requirements/`, `08-architecture/`, UML/Component diagrams | Clear separation of concerns, non-monolithic codebase, traceable requirements register. |
| **3. Data Engineering & Preprocessing**| **15 Marks** | Ingestion pipeline, imputation, categorical encoding, chronological splits | Zero data leakage, robust handling of missing sensors, correct temporal horizon formulation. |
| **4. Predictive Modeling & Evaluation** | **20 Marks** | `XGBoost` training, cross-validation, confusion matrices, F1 scores | Multi-class performance > 90%, rigorous evaluation beyond naive accuracy, comparison with baselines. |
| **5. Counterfactual Simulation & Policy** | **15 Marks** | Perturbation vectors ($\alpha, \beta$), transition matrices, action dispatch | Real-world policy simulation (what-if analysis), physical capacity constraints, actionable recommendations. |
| **6. Visual Dashboard & UI/UX** | **10 Marks** | Obsidian command center, interactive sliders, spatial heatmaps | High visual standard, tactile interactions, responsive layout, clear operational value for municipal engineers. |
| **7. Technical Defense & Viva Voice** | **10 Marks** | Prework synthesis, evidence ledger, architectural justification | Fluid explanation of why XGBoost was chosen, how simulation works, and why counterfactuals matter. |

---

## 2. Top-5 Academic Failure Risks & Mitigations

1. **Risk 1: Accusation of Look-Ahead Data Leakage**
   - *Failure:* Shuffling time-series observations randomly so future information leaks into training.
   - *Mitigation:* Strict temporal ordering and train-test splitting based on timestamp cut-offs.
2. **Risk 2: Unsubstantiated Model Accuracy Claims**
   - *Failure:* Claiming 99% accuracy on an imbalanced dataset where a dummy classifier gets 90%.
   - *Mitigation:* Report weighted Precision, Recall, F1, and multi-class confusion matrices across all classes (`Low`, `Moderate`, `High`, `Severe`).
3. **Risk 3: "Black Box" Simulation Without Grounding**
   - *Failure:* Arbitrary reductions without physical justification.
   - *Mitigation:* Ground 20% demand reduction ($\alpha=0.20$) in dynamic rerouting literature and 10% speed gain ($\beta=0.10$) in coordinated green-wave signal timing.
4. **Risk 4: AI Slop UI Aesthetic**
   - *Failure:* Standard generic Bootstrap or unstyled purple neon dashboard.
   - *Mitigation:* Obsidian palette (`#07080a`), Apple HIG materials, frosted glass cards, and high-contrast typographic hierarchy.
5. **Risk 5: Lack of Literature Traceability**
   - *Failure:* Inability to quote papers during viva.
   - *Mitigation:* All 10 papers mapped explicitly to specific equations, algorithms, and design choices.

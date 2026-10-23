# Scope Definition & Milestone Boundaries

**Author:** Principal System Orchestrator  
**Reviewers:** Senior Architecture Panel  

---

## 1. 50% Implementation Milestone vs 100% Target

```
[==================== 50% COMPLETED ====================|------------------- 50% TO SCALE -------------------]
   - Baseline Jupyter notebook (Untitled15.ipynb)          - Modular production package architecture
   - Initial XGBoost training and scoring                 - Fast REST/WebSocket serving API
   - 203k row dataset with simulated outcomes             - Standalone luxury obsidian command dashboard
   - Initial heuristic action recommendation              - Automated interactive policy simulation sliders
   - Basic matplotlib static charts                        - Comprehensive test suite & automated verification
```

---

## 2. In-Scope vs Out-of-Scope Deliverables

### In-Scope (Mandatory for 100% Capstone)
1. **End-to-End Modular Codebase:** Python package with clean sub-modules (`core/`, `pipeline/`, `models/`, `simulation/`, `dispatch/`, `ui/`).
2. **Model Persistence:** Serialized pipelines and label encoders allowing zero-downtime hot-reloading.
3. **Interactive Control Room UI:** Standalone, human-crafted web interface with real-time zone metrics, spatial corridor views, and interactive counterfactual sliders.
4. **Reproducible Test Suite:** Unit and integration tests covering data validation, prediction bounds, and simulation conservation laws.
5. **Academic Documentation:** Formal capstone artifacts including SRS, UML diagrams, ER diagrams, test reports, and viva defense scripts.

### Out-of-Scope (Cut-Line Safeguards)
1. **Direct Physical SCATS Hardware Actuation:** We do not physically connect to municipal street wiring; output is formatted as an operational API dispatch directive.
2. **Real-Time GPS Vehicle Flashing:** We model macroscopic road links and intersections, not individual vehicle micro-movements.
3. **Multi-City Cross-Country Deployment:** System is optimized and calibrated for the 6 metropolitan zones present in the project dataset.

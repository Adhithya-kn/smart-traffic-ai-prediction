# Implementation Plan & Engineering Execution Roadmap

**Author:** Principal System Orchestrator  
**Reviewer:** Senior Architecture Panel  

---

## 1. Phased Execution Roadmap

The completion of the system follows four concrete engineering phases:

```
+---------------------------------------------------------------------------------------------+
| PHASE 1: CORE ENGINE & PIPELINE REFACTORING                                                 |
| - Extract notebook logic into modular Python classes (Ingestion, Preprocessor, XGBoostModel)|
| - Build persistent serialization pipeline for trained artifacts (model.joblib, encoder.joblib)|
| - Achieve 100% test pass on feature transforms and inference                                |
+---------------------------------------------------------------------------------------------+
                                              |
                                              v
+---------------------------------------------------------------------------------------------+
| PHASE 2: COUNTERFACTUAL SIMULATION & PRESCRIPTIVE DISPATCH                                  |
| - Implement configurable PolicySimulator class with dynamic alpha and beta bounds          |
| - Build ActionDispatcher engine with priority ranking and multi-tier municipal directives   |
| - Verify transition impact matrices and boundary physical constraints                      |
+---------------------------------------------------------------------------------------------+
                                              |
                                              v
+---------------------------------------------------------------------------------------------+
| PHASE 3: HUMAN-CRAFTED OBSIDIAN COMMAND DASHBOARD                                           |
| - Build luxury obsidian control room interface (#07080a, frosted glass, Apple HIG tokens)   |
| - Implement real-time KPI tickers, interactive zone filter, and dynamic simulation sliders  |
| - Render interactive Before/After comparison and corridor congestion charts                 |
+---------------------------------------------------------------------------------------------+
                                              |
                                              v
+---------------------------------------------------------------------------------------------+
| PHASE 4: VERIFICATION, TESTING & ACADEMIC DEFENSE PREPARATION                               |
| - Execute automated MCP inspection via traffic-inspector                                    |
| - Generate formal academic artifacts (SRS, Architecture, Use Cases, Viva Defense Script)    |
| - Package demo script and user manual                                                       |
+---------------------------------------------------------------------------------------------+
```

---

## 2. Cut-Line Ladder & Contingency Plan

If time or user constraints arise, features will be gracefully degraded in reverse order:
- **Cut-Line 1 (Low Risk):** Static visual charts replace dynamic animated WebGL overlays.
- **Cut-Line 2 (Medium Risk):** Simulation sliders operate on pre-computed discrete steps (10%, 20%, 30%) instead of arbitrary continuous floats.
- **Core Floor (Non-Negotiable):** Complete modular Python codebase, XGBoost predictive model, counterfactual simulation verification, and luxury obsidian UI.

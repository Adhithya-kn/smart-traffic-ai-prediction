# Research Protocol & Evidence Taxonomy

## 1. Evidence Classification Taxonomy

Every statement, metric, claim, or architectural decision within the project repository MUST carry an explicit evidence tag:

| Tag | Evidence Category | Description | Authority / Reliability |
| :---: | :--- | :--- | :---: |
| **`[D]`** | **Dataset Telemetry** | Derived directly from raw records in `Dataset/traffic_prediction_results (1) best one.csv`. | **Absolute Ground Truth** |
| **`[L]`** | **Academic Literature** | Directly cited from one of the 10 peer-reviewed papers in `Literature/`. | **High Peer-Reviewed** |
| **`[S]`** | **Sample 50% Notebook** | Code logic, parameters, or transforms extracted from `sample of 50% implemenatation/Untitled15.ipynb`. | **Empirical Baseline** |
| **`[V]`** | **Automated MCP Audit** | Verified programmatically via the `traffic-inspector` MCP server tools. | **Audited / Certified** |
| **`[A]`** | **Architectural Assumption** | An engineering premise or parameter adopted in the absence of explicit data. Must be logged. | **Provisional (Audited)** |

---

## 2. Prohibition on Hallucination & Pseudo-Data
- **FORBIDDEN:** Inventing performance metrics, quoting papers not in `Literature/`, assuming sensor accuracies without citation, or fabricating telemetry columns.
- **MANDATORY:** If a parameter is unknown or not stated in the source dataset, it MUST be tagged `[A]` and recorded in `prework-research/12-evidence/OPEN_QUESTIONS.md`.

---

## 3. Literature Citation Format
When referencing academic sources, always provide:
1. Paper filename and official title.
2. Specific section, equation, or page number.
3. Concrete contribution to our architecture (e.g., risk scoring formula, GNN topology, or delay quantification).

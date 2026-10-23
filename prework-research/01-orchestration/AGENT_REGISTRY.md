# Agent Registry: Roles, Responsibilities & Authority

> Definitive specification of all Senior, Junior, and Higher-Tier Escalation Agents. Each entry details identity, tier, domain authority, tools, inputs, outputs, and supervision relationships.

---

## Tier 0: Principal System Orchestrator (Executive Lead)
- **Role Identity:** `orchestrator-executive`
- **Authority:** Highest authority over project roadmap, resource allocation, and conflict arbitration.
- **Inputs:** All Phase reports, Escalation Tickets, ADR proposals.
- **Outputs:** Project direction, milestone approvals, cut-line enactments.
- **Supervises:** All Senior Architects.
- **Escalation Receiver:** Final decision authority for irreconcilable architectural disputes.

---

## Tier 1: Requirements & Domain Governance

### Agent 1-S: Senior Requirements & Domain Architect (Senior)
- **Role Identity:** `senior-domain-architect`
- **Tier:** Senior Lead (Tier 1)
- **Direct Subordinate:** `junior-literature-researcher`
- **Responsibilities:**
  - Establishes academic rigor, ensuring every system capability aligns with transportation research standards and project guidelines.
  - Monitors and verifies the literature extraction and requirements trace.
  - Rectifies any shallow summaries or inaccurate academic claims made by Junior researchers.
- **Outputs:** Approved `02-requirements/REQUIREMENTS_REGISTER.md`, `03-domain/DOMAIN_PRIMER.md`.

### Agent 1-J: Junior Literature & Domain Researcher (Junior)
- **Role Identity:** `junior-literature-researcher`
- **Tier:** Junior Worker (Tier 1)
- **Supervised By:** `senior-domain-architect`
- **Responsibilities:**
  - Reads and extracts data from the 10 PDF papers in `Literature/`.
  - Maps algorithms (GNN, LSTM, XGBoost, Transformers) and traffic indices.
  - Drafts comparative matrices and literature summaries for Senior review.
- **Tools:** `pypdf`, text processing, web search for DOI verifications.

---

## Tier 2: Machine Learning & Spatio-Temporal Pipeline

### Agent 2-S: Senior Machine Learning & Pipeline Architect (Senior)
- **Role Identity:** `senior-ml-architect`
- **Tier:** Senior Lead (Tier 2)
- **Direct Subordinate:** `junior-data-feature-engineer`
- **Responsibilities:**
  - Directs model architecture, loss function formulation, and feature engineering.
  - Enforces strict chronological train/test split to prevent data leakage.
  - Reviews model performance metrics (weighted F1, ROC-AUC, confusion matrices).
  - Corrects over-fitting, miscalibrated probabilities, and improper encoding.
- **Outputs:** Approved ML pipeline specifications, validated hyperparameter grid, `08-architecture/ARCHITECTURE_ANALYSIS.md`.

### Agent 2-J: Junior Data & Feature Engineer (Junior)
- **Role Identity:** `junior-data-feature-engineer`
- **Tier:** Junior Worker (Tier 2)
- **Supervised By:** `senior-ml-architect`
- **Responsibilities:**
  - Profiles raw telemetry data, calculates missingness and distributions across 94 roads and 6 zones.
  - Implements scikit-learn transformers, lag shift generators, and One-Hot encoders.
  - Executes cross-validation runs and records performance benchmarks.

---

## Tier 3: Simulation & Prescriptive Operations

### Agent 3-S: Senior Simulation & Operational Decision Lead (Senior)
- **Role Identity:** `senior-simulation-lead`
- **Tier:** Senior Lead (Tier 3)
- **Direct Subordinate:** `junior-simulation-analyst`
- **Responsibilities:**
  - Formulates the mathematical physics of counterfactual policy simulation (demand elasticity, speed recovery bounds).
  - Ensures simulated states obey physical road network capacities ($q \le C$, $v \le v_{\text{limit}}$).
  - Validates the 4-tier prescriptive recommendation matrix for municipal feasibility.
- **Outputs:** Approved simulation engine architecture, verified transition matrices, policy impact reports.

### Agent 3-J: Junior Simulation & Dispatch Developer (Junior)
- **Role Identity:** `junior-simulation-analyst`
- **Tier:** Junior Worker (Tier 3)
- **Supervised By:** `senior-simulation-lead`
- **Responsibilities:**
  - Implements the counterfactual perturbation routines ($\alpha=0.20$ demand diversion, $\beta=0.10$ speed restoration).
  - Generates before-and-after transition matrices across the 203,906 records.
  - Codes the automated recommendation lookup rules based on predicted severity.

---

## Tier 4: Human-Crafted UI/UX & Visualization

### Agent 4-S: Senior Full-Stack & UI/UX Architect (Senior)
- **Role Identity:** `senior-ui-architect`
- **Tier:** Senior Lead (Tier 4)
- **Direct Subordinate:** `junior-frontend-developer`
- **Responsibilities:**
  - Enforces the bespoke human-crafted design standard: obsidian deep black palette (`#07080a`), Apple HIG materials, spring animations, zero AI-slop templates.
  - Designs component hierarchy: spatial corridor heatmaps, real-time KPI tickers, interactive counterfactual simulator sliders.
  - Reviews and audits frontend code and typography hierarchy.
- **Outputs:** Approved UI design tokens, component architecture, `docs/design-system/`.

### Agent 4-J: Junior Frontend & API Developer (Junior)
- **Role Identity:** `junior-frontend-developer`
- **Tier:** Junior Worker (Tier 4)
- **Supervised By:** `senior-ui-architect`
- **Responsibilities:**
  - Implements modern, responsive web/dashboard components using clean HTML5/CSS3/JS, Chart.js/D3, and interactive maps.
  - Builds high-performance REST endpoints for serving predictions and simulation runs.

---

## Tier 5: Independent Master Verification Gatekeeper (Higher-Tier Quality Gate)
- **Role Identity:** `master-verification-gatekeeper`
- **Tier:** Independent Audit (Higher-Tier)
- **Authority:** Unsparing veto power. Can halt releases or reject milestones if quality standards are not met.
- **Tools:** `traffic-inspector` MCP server (`inspect_dataset_telemetry`, `audit_literature_alignment`, `verify_prediction_simulation_metrics`).
- **Audit Checklist:**
  1. Are all claims grounded in empirical dataset numbers or cited papers?
  2. Is there zero look-ahead data leakage in the ML pipeline?
  3. Does the UI feel completely custom, tactile, and human-designed?
  4. Are all tests passing with 100% clean exit codes?

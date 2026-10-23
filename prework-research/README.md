# Pre-Work Research — AI-Based Smart Traffic Monitoring & Congestion Prediction System

**Course:** B.Tech Design Project (Capstone Engineering)  
**Topic:** AI-Based Smart Traffic Monitoring and Congestion Prediction System  
**Status:** Pre-work foundational structure established — Multi-Agent Orchestration & Domain Verification Active  
**Reference Pillar:** Inspired by the rigorous engineering and evidence-backed structure of the Enterprise Reference Architecture (`CUDA.zip`)  
**Read first:** [`00-project-brief/PROJECT_BRIEF.md`](00-project-brief/PROJECT_BRIEF.md) → [`13-synthesis/FINAL_SYNTHESIS.md`](13-synthesis/FINAL_SYNTHESIS.md)

---

## 1. What This Is

A complete, evidence-backed pre-work architecture and investigative research body establishing:
- **What the project is** and the precise real-world problem it solves.
- **What academic literature and prior art exist** (grounded in our 10 peer-reviewed papers).
- **What is genuinely new** (the bridge between predictive traffic classification and counterfactual mitigation simulation).
- **How it is structured and engineered** before scaling implementation.
- **How senior and junior agents collaborate, audit, and escalate** to maintain human-crafted quality without AI slop.

Every file in this directory represents a specialized deliverable adhering to strict evidence tags:
- `[D]` = Verified directly against the 203,906 records in `Dataset/`.
- `[L]` = Sourced from peer-reviewed literature in `Literature/`.
- `[S]` = Extracted from the 50% baseline notebook in `sample of 50% implemenatation/`.
- `[V]` = Verified via automated MCP tools (`traffic-inspector`).
- `[A]` = Stated architectural assumption subject to review.

---

## 2. The Three-Line Executive Summary

1. **What:** A high-throughput, spatio-temporal smart traffic monitoring and predictive intelligence platform that forecasts road-level congestion states (`Low`, `Moderate`, `High`, `Severe`) across 94 urban road segments and 100 intersections spanning 6 distinct city zones.
2. **The Innovation Gap:** Standard traffic systems either provide passive real-time reporting (Google Maps/Waze) or theoretical open-loop forecasting without actionable prescriptive intervention. Our system couples gradient-boosted multi-class horizon forecasting with an active **counterfactual simulation core** (20% demand dampening, 10% speed gain) and an automated **operational recommendation dispatch engine**.
3. **The Engineering Standard:** Strictly structured, non-monolithic, modular architecture built on multi-tier agent supervision (Senior oversight of Junior deliverables, escalation protocols, and automated MCP quality gates).

---

## 3. Directory Blueprint

```
prework-research/
├── README.md                                   ← You are here
├── 00-project-brief/
│   └── PROJECT_BRIEF.md                        Central source of truth — READ FIRST
├── 01-orchestration/
│   ├── ORCHESTRATION_PLAN.md                   Multi-agent hierarchy & review pipeline
│   ├── AGENT_REGISTRY.md                       Definitive Senior & Junior agent roles
│   ├── HANDOFF_PROTOCOL.md                     Context transfer & fact preservation
│   ├── RESEARCH_PROTOCOL.md                    Evidence taxonomy & confidence rubric
│   └── TEMPLATES.md                            Standard reporting templates
├── 02-requirements/
│   ├── REQUIREMENTS_REGISTER.md                Functional & non-functional requirements
│   └── EVALUATION_MODEL.md                     Grading rubric & mark allocation model
├── 03-domain/
│   └── DOMAIN_PRIMER.md                        Traffic flow physics (MFD, Greenshields, LOS)
├── 04-problem/
│   └── PROBLEM_STATEMENT.md                    Core problem, root causes & assumptions
├── 05-prior-art/
│   ├── LITERATURE_REVIEW.md                    10-paper academic synthesis
│   └── PRIOR_ART_LANDSCAPE.md                  Comparative matrix against existing tools
├── 06-gap/
│   └── GAP_ANALYSIS.md                         Academic & engineering contribution gap
├── 07-technology/
│   └── TECH_STACK_FEASIBILITY.md               ML, backend, simulation & UI stack analysis
├── 08-architecture/
│   ├── ARCHITECTURE_ANALYSIS.md                End-to-end layered architecture & pipelines
│   └── DATA_MODEL_ANALYSIS.md                  Schema, entities, relationships & indices
├── 09-scope/
│   └── SCOPE_DEFINITION.md                     50% baseline vs 100% completion bounds
├── 10-decisions/
│   ├── ALTERNATIVES_ANALYSIS.md                Model & framework trade-offs
│   └── DECISION_LOG.md                         Architecture Decision Records (ADRs)
├── 11-plan/
│   └── IMPLEMENTATION_PLAN.md                  Phased execution milestones & cut-lines
├── 12-evidence/
│   ├── DATASET_AND_MODEL_AUDIT.md              Empirical telemetry & notebook verification
│   ├── EVIDENCE_LOG.md                         Catalog of verified facts
│   └── OPEN_QUESTIONS.md                       Decisions pending user guidance
└── 13-synthesis/
    └── FINAL_SYNTHESIS.md                      Comprehensive synthesis & project verdict
```

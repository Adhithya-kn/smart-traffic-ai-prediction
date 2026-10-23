# Multi-Agent Orchestration Plan: Smart Traffic AI System

## 1. Orchestration Philosophy & Principles

The development of this project strictly follows a **hierarchical peer-supervision model**:
1. **Senior-Junior Pair Structure**: Every technical domain is assigned a Senior Architect paired with a Junior Developer/Researcher.
2. **Review & Correction Mandate**: Juniors produce draft implementations, analysis tables, and preliminary code; Seniors thoroughly review, identify errors, refine logic, and rectify discrepancies before signing off.
3. **Higher-Tier Escalation**: If a Senior identifies an architectural conflict, statistical leakage, or physics violation that cannot be locally resolved, the issue is escalated to the **Principal System Orchestrator** and audited by the **Independent Master Verification Gatekeeper**.
4. **Context-Preserving Linear Flow**: Knowledge transfers sequentially through formal `HANDOFF` blocks to prevent hallucination, forgotten requirements, or context drift.

```
                           +---------------------------------------------+
                           |     PRINCIPAL SYSTEM ORCHESTRATOR           |
                           |   (Global Governance, Scope, Cut-Lines)     |
                           +---------------------------------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                       |                                       |
         v                                       v                                       v
+-----------------------+               +-----------------------+               +-----------------------+
|  SENIOR DOMAIN &      |               |  SENIOR ML & DATA     |               |  SENIOR SIMULATION &  |
|  REQUIREMENTS LEAD    |               |  PIPELINE ARCHITECT   |               |  DECISION LEAD        |
+-----------------------+               +-----------------------+               +-----------------------+
         | (Monitors & Corrects)                 | (Monitors & Corrects)                 | (Monitors & Corrects)
         v                                       v                                       v
+-----------------------+               +-----------------------+               +-----------------------+
|  Junior Literature &  |               |  Junior Data &        |               |  Junior Simulation &  |
|  Domain Researcher    |               |  Feature Engineer     |               |  Dispatch Developer   |
+-----------------------+               +-----------------------+               +-----------------------+
         |                                       |                                       |
         +---------------------------------------+---------------------------------------+
                                                 |
                                                 v
                           +---------------------------------------------+
                           |  SENIOR FULL-STACK & UI/UX ARCHITECT        |
                           |  (Obsidian Palette, Human Tactile Design)   |
                           +---------------------------------------------+
                                                 | (Monitors & Corrects)
                                                 v
                           +---------------------------------------------+
                           |  Junior Frontend & API Developer            |
                           +---------------------------------------------+
                                                 |
                                                 v
                           +---------------------------------------------+
                           |  INDEPENDENT MASTER VERIFICATION GATEKEEPER |
                           |  (MCP Tools, Automated Audits, Final Sign-off|
                           +---------------------------------------------+
```

---

## 2. Six-Phase Execution Pipeline

| Phase | Core Deliverable | Senior Lead | Junior Worker | Review & Sign-off Gate |
| :--- | :--- | :--- | :--- | :--- |
| **Phase A: Evidence & Requirements** | `00-project-brief/`, `02-requirements/` | Senior Requirements Lead | Junior Domain Researcher | Traced requirement register with 100% source citations |
| **Phase B: Domain & Prior-Art** | `03-domain/`, `04-problem/`, `05-prior-art/`, `06-gap/` | Senior Domain Lead | Junior Literature Researcher | 10-paper cross-comparison matrix & identified innovation gap |
| **Phase C: Technical Blueprint** | `07-technology/`, `08-architecture/`, `10-decisions/` | Senior ML Architect | Junior Feature Engineer | Layered component boundaries, ADRs, zero circular dependencies |
| **Phase D: Scope & Planning** | `09-scope/`, `11-plan/` | Principal Orchestrator | Junior Implementation Planner | Cut-line ladder, 50% baseline consolidation to 100% milestone |
| **Phase E: Empirical Audit** | `12-evidence/DATASET_AND_MODEL_AUDIT.md` | Master Quality Gatekeeper | Junior Data Engineer | Automated `traffic-inspector` MCP verification of 203,906 rows |
| **Phase F: Master Synthesis** | `13-synthesis/FINAL_SYNTHESIS.md` | Principal Orchestrator | Senior Review Panel | Formal Project Charter & GO Verdict |

---

## 3. Supervision, Review & Escalation Contract

### 3.1 Junior Obligation
- Produces artifacts conforming to standard templates (`prework-research/01-orchestration/TEMPLATES.md`).
- Explicitly flags every assumption with `[A]` and marks uncertain parameters with `[OPEN_QUESTION]`.
- Hands off work to Senior using the formal four-part handover format:
  1. `SETTLED FACTS`
  2. `CONSTRAINTS`
  3. `IDENTIFIED DEFICIENCIES`
  4. `PROPOSED CORRECTIONS`

### 3.2 Senior Obligation
- Reviews Junior output within the specific domain for technical rigor, mathematical validity, and absence of generic template filler.
- If errors exist (e.g., look-ahead data leakage, unphysical traffic flow, ungrounded metrics), the Senior **rejects the draft with line-by-line corrective actions** or rewrites the critical sections directly.
- Signs off with a formal `REVIEW VERDICT`: `APPROVED`, `REVISE`, or `ESCALATE`.

### 3.3 Escalation Protocol
- If a problem involves cross-domain conflicts (e.g., ML feature requirement conflicts with real-time UI latency limits or simulation speed calculation violates physical roadway bounds), the Senior raises an `ESCALATION TICKET` to the **Principal System Orchestrator**.
- The Principal Orchestrator convenes the Senior panel, issues an **Architecture Decision Record (ADR)** in `10-decisions/`, and records the resolution in `12-evidence/SHARED_CONTEXT.md`.

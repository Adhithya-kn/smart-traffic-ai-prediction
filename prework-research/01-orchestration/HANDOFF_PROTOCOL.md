# Handoff Protocol & Context Preservation

## 1. The Handoff Contract
To eliminate hallucinations, context amnesia, or uncoordinated assumptions between agents, every completed phase or sub-task MUST conclude with a standardized **HANDOFF BLOCK**.

A receiving agent is strictly forbidden from starting execution without verifying and ingesting the handoff from the preceding agent.

---

## 2. Standard Handoff Format

```markdown
---
### AGENT HANDOFF BLOCK
- **From Agent:** [e.g., junior-literature-researcher]
- **To Agent:** [e.g., senior-domain-architect]
- **Phase / Deliverable:** [e.g., Phase B — 05-prior-art/LITERATURE_REVIEW.md]
- **Date / Timestamp:** [ISO 8601 Timestamp]

#### 1. Settled Facts (Grounded & Verified)
- [Fact 1 with tag [D], [L], or [V]]
- [Fact 2 with tag [D], [L], or [V]]

#### 2. Established Invariants & Constraints
- [Constraint 1: e.g., chronological split only, no random k-fold shuffling]
- [Constraint 2: e.g., demand reduction factor capped at 0.30]

#### 3. Identified Discrepancies / Deficiencies
- [Deficiency 1: What was missing or found problematic in draft]

#### 4. Corrective Action Taken / Required
- [Correction 1: How the issue was resolved or needs review]

#### 5. Open Questions for Senior Lead / User
- [Open question 1 requiring human or architectural decision]
---
```

---

## 3. Senior Review Verdict Protocol

Upon receiving a Junior handoff block, the Senior Architect must evaluate the work against the domain rubric and stamp one of three formal verdicts:

1. **`APPROVED`**: The deliverable meets all theoretical, mathematical, and aesthetic criteria. It is committed to the shared repository and passed to the next phase.
2. **`REVISE`**: The Senior provides a prioritized defect list. The Junior worker must implement the revisions within the same phase cycle.
3. **`ESCALATE`**: The issue represents a systemic contradiction or requires executive trade-offs. The ticket is immediately escalated to the Principal System Orchestrator.

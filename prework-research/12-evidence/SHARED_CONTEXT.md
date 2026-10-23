# Shared Context & Working Memory

**Project:** AI-Based Smart Traffic Monitoring and Congestion Prediction System  
**Last Updated:** 2026-10-22  
**Active State:** Pre-Work Research Complete — Orchestration & MCP Verified  

---

## 1. Settled Baseline Facts
1. The project has a verified dataset with 203,906 rows across 94 roads, 100 intersections, and 6 city zones (`Dataset/`).
2. The baseline model is an XGBoost multi-class classifier achieving 94.79% prediction match on the horizon target (`sample of 50% implemenatation/`).
3. Counterfactual mitigation simulation with $\alpha=0.20$ (demand reduction) and $\beta=0.10$ (speed recovery) resolves 3,052 Severe congestion bottlenecks.
4. The reference project (`CUDA.zip`) provides the structural and governance pillar: multi-agent supervision (Senior/Junior), handoff contracts, and non-monolithic modular engineering.

---

## 2. Active Technical Invariants
1. All training must respect strict chronological ordering to prevent look-ahead bias.
2. The UI must follow the obsidian dark standard (`#07080a`) with Apple HIG frosted glass cards and tactile feedback.
3. Automated verification must be continuously maintained via the `traffic-inspector` MCP server.

# Evidence Log: Verified Ground-Truth Claims

| ID | Verified Fact / Claim | Grounding Source | Verification Method |
| :---: | :--- | :--- | :--- |
| **EV-001** | Dataset contains exactly 203,906 rows across 12 feature attributes. | `Dataset/traffic_prediction_results (1) best one.csv` | Programmatic pandas count `[D, V]` |
| **EV-002** | The network spans 94 unique roads and 100 intersections in 6 city zones. | `Dataset/traffic_prediction_results (1) best one.csv` | `traffic-inspector` MCP `[D, V]` |
| **EV-003** | Baseline model achieves 94.79% raw prediction match rate against future targets. | Baseline dataset & notebook | `traffic_inspector_mcp.py` `[S, V]` |
| **EV-004** | Counterfactual policy reduces Severe congestion by 3,052 segments (5,949 net improved). | Transition matrix calculation | `traffic_inspector_mcp.py` `[S, V]` |
| **EV-005** | Tree ensemble algorithms outperform neural nets on tabular sensor data. | Papers 3 and 5 | Peer-reviewed citations `[L]` |
| **EV-006** | Rainfall causes 12% to 22% capacity degradation on urban road segments. | Paper 6 (Nature Scientific Reports) | Direct paper equation `[L]` |

# Open Questions & Decision Ledger

> Explicit ledger of design parameters and upcoming user choices, preventing implicit assumptions.

---

### OQ-001: Serving Framework Preference
- **Question:** Do you prefer the control room interface to be hosted as a standalone, zero-dependency modern HTML/CSS/JS web dashboard, a Python Streamlit app, or a FastAPI + web client?
- **Current Default:** High-performance, zero-dependency Obsidian HTML5/CSS3/Vanilla JS dashboard connected to lightweight Python processing, providing Apple HIG luxury aesthetics.
- **Status:** OPEN for user confirmation.

### OQ-002: Spatial Mapping Visualizer
- **Question:** Should road segments be visualized on an interactive stylized canvas map (coordinate topology) or an integrated Leaflet/OpenStreetMap layer?
- **Current Default:** Stylized interactive SVG/Canvas corridor grid with zone overlays, ensuring zero external API key requirements.
- **Status:** OPEN for user confirmation.

### OQ-003: Model Retraining Interface
- **Question:** Do you want the system to include a one-click retraining button in the UI to retrain XGBoost on freshly uploaded CSV files?
- **Current Default:** Yes, pipeline script will support both batch inference and automated retraining.
- **Status:** OPEN for user confirmation.

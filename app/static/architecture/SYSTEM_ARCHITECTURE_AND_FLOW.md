# System Architecture & Data Flow (Current Truth)

> **Status:** functional capstone prototype, not production. This file replaces the previous overclaiming architecture document. The authoritative product direction is [`../docs/VISION.md`](../docs/VISION.md); the current-state audit is [`../docs/AUDIT_REPORT.md`](../docs/AUDIT_REPORT.md).

---

## 1. Scope

The system is an advisory traffic platform for Bengaluru-style mixed traffic. It has two roles:

- **Traffic Management:** monitor corridors, upload/analyse camera clips, view next-hour forecasts, receive Webster signal-timing advisories and route advisories.
- **Road User:** plan a trip, view predicted congestion on the direct route, and receive an alternate-route advisory.

It does **not** actuate physical traffic signals. It does not have a validated live-CCTV feed today; it processes uploaded or recorded video. It does not yet have a validated physical vehicle-density measurement.

---

## 2. Current architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ Presentation: app/static (canonical) → public (generated mirror)    │
│   Login · Monitor · CV · Predict/Map · Decisions · Trip             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP JSON / static / video Range
┌───────────────────────────────▼─────────────────────────────────────┐
│ app/server.py: ThreadingHTTPServer + routes                          │
│   auth · roads/events · predictions · live fallback · CV job API    │
│   vision_routes.py: upload → job → results → video                   │
└───────┬───────────────────────┬─────────────────────┬───────────────┘
        │                       │                     │
        ▼                       ▼                     ▼
┌───────────────┐   ┌───────────────────────┐  ┌──────────────────────┐
│ CV subsystem  │   │ ML / data subsystem   │  │ Live / decision       │
│ detector      │   │ XGBoost predictor     │  │ TomTom/weather bridge │
│ tracker       │   │ pure-Python trees     │  │ event manager         │
│ counter       │   │ topology/metrics      │  │ Dijkstra/BPR routing  │
│ speed/density │   │ synthetic benchmark   │  │ Webster/Greenshields  │
│ incidents     │   │                       │  │ dispatch/directives   │
│ job manager   │   │                       │  │                       │
└───────┬───────┘   └──────────┬────────────┘  └──────────┬───────────┘
        │                      │                          │
        ▼                      ▼                          ▼
  annotated MP4         forecast + probabilities     route/signal advisory
  JSON metrics          baselines in audit            fallback tagged
```

### Runtime facts
- Web server: Python standard-library `ThreadingHTTPServer`; no FastAPI/Django/Flask.
- Persistence: JSON files/artifacts; no SQL database.
- ML: XGBoost 80 rounds × 4 classes; pure-Python tree JSON used at runtime for fast inference.
- CV: Ultralytics YOLO11n (stock COCO weights), custom IoU tracker, heuristic occupancy/speed/incident logic.
- Data: 57,600-row **synthetic** hourly benchmark, 24 corridors/8 zones/100 days (2022); not real Kaggle observations.
- Live data: TomTom/Open-Meteo are currently misconfigured and fall back to empirical baselines; fallbacks are tagged in the API, but the UI has shown them as “live”.
- Routing graph: 24 corridor nodes; path is a simplified 2–3-corridor sequence, not a full road network.
- Deployment: Render/Docker for the full app; Vercel is static/demo only and cannot run the CV workload.

---

## 3. Target data flow

```
Camera/clip
  → camera registry + ROI/lane polygons + 4-point homography
  → fine-tuned Indian-traffic detector
  → ByteTrack/BoT-SORT tracker + line-crossing counter
  → TrafficMeasurement (counts, flow, occupancy, calibrated/proxy speed,
     density, incidents, calibration/model/provenance)
  → traffic state store (corridor + capture time + quality flags)
  → XGBoost next-hour forecast (measured features, baselines, OOD rejection)
  → Webster seed/split advisory + Dijkstra route advisory
  → dashboard (Monitor / Predict / Decide / Evaluation)
```

**Rules:**
1. Uncalibrated CV values are label `proxy`/`uncalibrated` and are excluded from prediction, signal, and route decisions.
2. Missing/invalid measured fields cause a 4xx, not a fabricated default.
3. Every response carries provenance: live/cached/historical/simulated + model/calibration IDs.
4. CV detection accuracy and dashboard responsiveness are measured deliverables.

---

## 4. Current known gaps (short list)

- CV: no fine-tuning, no auto-rickshaw class, no mAP/annotations, no calibrated speed/density, noisy incidents, custom tracker/counter defects.
- CV→ML: measured counts/PCU are discarded; volume is a static baseline × occupancy heuristic; capacity-utilization bug (lanes passed as capacity) pins 100%; “15m” label vs 1h model.
- ML: synthetic benchmark; 86.98% only +0.22pp over a lookup; no baseline in README/UI; silent predictor defaults.
- Live: provider base URLs are web-console pages; weather placeholder key causes 400; fallback status misdiagnosed.
- UI/API: responsive header broken, dead Live-CCTV JS, `/live_traffic` 404, demo-session auth bypass, unauthenticated admin writes when enforcement off, no heat overlay, hardcoded KPIs.
- Tests/repo: clean-clone suite has one env-dependent failure; tests mutate tracked artifacts; 74% coverage; no CI; Docker/Vercel claim drift.

---

## 5. Design decisions

- Keep the working XGBoost/routing/Webster/auth/upload engineering; do not rewrite for novelty.
- Replace the heuristic CV→ML mapping with a measured `TrafficMeasurement` contract.
- Use a fine-tuned YOLO11s/m detector with Indian classes; use ByteTrack/BoT-SORT and calibration instead of the current custom IoU/occupancy proxies.
- Make evaluation a product feature, not a README paragraph.
- Remove out-of-scope dev tooling (synthesizer/API-key studio/synthetic stress lab) from the main product UI.
- One canonical static source (`app/static`) and one architecture source; generated mirrors are build artifacts.

See [`../docs/VISION.md`](../docs/VISION.md) for the full contract, metrics, and phase gates.

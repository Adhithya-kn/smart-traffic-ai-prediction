# Phase 0 Verification — Truth Reset & Stabilization

**Date:** 2026-11-04
**Status:** complete for the implemented scope
**Baseline audit:** [`AUDIT_REPORT.md`](AUDIT_REPORT.md)
**Vision:** [`VISION.md`](VISION.md)

> This is verification of the Phase 0 work, not a claim that the CV/ML objectives are complete. Phase 1 (evaluated Indian-traffic CV) is blocked on licensed footage/annotation and is the next milestone.

---

## 1. Delivered

### Documentation
- `docs/VISION.md` — product vision, measurement contract, roadmap, evaluation gates.
- `docs/AUDIT_REPORT.md` — evidence-backed current-state audit.
- `docs/requirements/378_Design Project Problem Statement_6_Rashmi Mothkur.docx` — tracked official statement.
- `README.md`, `PROJECT_STRUCTURE.md`, `Dataset/README.md`, `architecture/SYSTEM_ARCHITECTURE_AND_FLOW.md` rewritten to match reality.
- Stale `PROJECT.md` restructuring plan archived under `docs/archive/`.
- Stale `visual_architecture.html` / `beginner_guide.html` carry an “OUTDATED EVIDENCE” banner.

### UI
- Responsive header at 1280/1440/1920: no horizontal scroll, no overlapping role badge, Sign Out visible.
- Consolidation to authority tabs **Monitor / CV Monitor / Predict / Decide**; commuter **Monitor / Traffic / Predict**.
- Removed Synthesizer tab/route (redirects to `/portal`), haptic audio, unverified bundled-sample selector, dead Live-CCTV JS, undefined `startClientInferenceLoop`.
- Fixed incident key mismatch; incident count now reflects the backend (honest “unvalidated heuristic events”).
- Removed hardcoded KPIs; model accuracy bound from `/api/metrics`.
- Replaced deprecated Google `HeatmapLayer` with weighted circles and explicit empirical/proxy labeling.
- Removed fake demo session; `/portal` without a real session redirects to `/login`.
- Corrected cache-busting to `?v=2.5`.

### API / security / config
- Anonymous admin mutations now return 401 even when `ENFORCE_ADMIN_AUTH` is relaxed; explicit `ALLOW_ANONYMOUS_ADMIN` opt-in required.
- `/live_traffic` and new `/decide`, `/predict`, `/monitor` routes served; `/synthesizer` redirects.
- `HEAD /api/health` returns 200.
- Runtime JSON state (`users/events/jobs/sessions/incidents`) moved to `var/` or `<PERSISTENT_DATA_DIR>/runtime`; seed files remain immutable. Tracked artifacts were not used by the verification server.
- Fixed provider base URLs in `.env` (TomTom/Google) and stopped sending an `X-Api-Key` header to keyless Open-Meteo.
- Empty/partial CV advisory payloads now return 400 instead of fabricating defaults.
- Capacity utilization no longer passes lane count as capacity in the CV advisory path; output key is `next_hour_forecast`; provenance is marked uploaded-video/uncalibrated.

### Tests / repo
- `tests/conftest.py` isolates runtime state to a temp dir before config import; tests no longer truncate tracked artifacts.
- Heavy North-East video test is opt-in (`RUN_HEAVY_VIDEO_TEST=1 pytest -m integration`) and skips by default.
- Added `cryptography`; pinned/updated requirements; added CI workflow.
- `.dockerignore` no longer excludes `architecture/`; `var/` ignored.
- Static `app/static` and generated `public` are in sync.

---

## 2. Verification evidence

```text
$ pytest -q
213 passed, 4 skipped in 40.12s
# 4 skipped = 3 live-API + 1 opt-in heavy video; 217 collected

$ pytest -m "not integration" -q
213 passed, 4 deselected in 41.18s

$ python3 scripts/sync_static.py --check
[OK] All static assets in public/ are in sync with app/static/

$ node --check app/static/app.js
# exit 0

$ curl -X POST /api/events/add without token
HTTP 401

$ curl -I /api/health
HTTP/1.0 200 OK

$ GET /synthesizer
-> redirects to /portal
```

Playwright (isolated server on port 8090):
- 1280/1440/1920: `scrollWidth == innerWidth`, Sign Out visible; no page errors; no console errors.
- Authority nav: Monitor, CV Monitor, Predict, Decide.
- Commuter nav: Monitor, Traffic, Predict.
- Direct `/portal` with no session redirects to `/login`.
- CV upload of `sample_traffic.mp4` completes; results show `49 Active` heuristic incidents (honest), `PCU Flow (short-clip estimate)`, `Density: requires calibration`, engine `Ultralytics yolo11n.pt (MPS)`.
- Evidence screenshots: [`evidence/phase0_monitor_1280.png`](evidence/phase0_monitor_1280.png), [`evidence/phase0_cv_monitor.png`](evidence/phase0_cv_monitor.png), [`evidence/phase0_commuter_1280.png`](evidence/phase0_commuter_1280.png), [`evidence/phase0_predict_proxy_heatmap.png`](evidence/phase0_predict_proxy_heatmap.png), [`evidence/phase0_final_1440.png`](evidence/phase0_final_1440.png).

---

## 3. Known remaining issues (Phase 1/2)

- CV still uses stock COCO YOLO11n; no auto-rickshaw class, no fine-tuning, no mAP/annotations. Objective 2/6 remain **partial**.
- Speed/density remain uncalibrated; UI labels them proxy/requires calibration.
- Incident metrics are heuristic and unvalidated; they are now visible, not hidden.
- CV→ML still uses an occupancy→baseline-volume heuristic; `capacity_utilization` is fixed but measured PCU is not yet the model input.
- The 86.98% model remains a synthetic-benchmark result; baselines are documented in the audit, not yet exposed in the UI.
- Live TomTom/weather remain fallback; base URLs are fixed but keys/reachability must be verified.
- `traffic_system/artifacts/{users,events,vision_jobs}.json` are still tracked runtime files and were modified by the user’s long-running 8081 server during Phase 0. Phase 4 should move these to ignored seeds/runtime and stop tracking them; do not disrupt the live process to do it.
- Vercel/CV limits and Docker deployment verification remain Phase 4.

---

## 4. Phase 1 next step

1. Obtain/licence 3–5 Indian traffic clips (Bengaluru preferred; otherwise public Indian dataset with a stated domain gap).
2. Annotate 1,500–3,000 frames for `{car, motorcycle, auto_rickshaw, bus, LCV/truck, bicycle, pedestrian}`; video-level split.
3. Fine-tune YOLO11s/m at imgsz 960–1280; commit weights/config.
4. Run `scripts/eval_cv.py` (to be added) and publish mAP50/mAP50-95, per-class P/R/F1, count MAE, IDF1/MOTA.
5. Only then update the CV claims from “demo” to “evaluated”; do not claim accuracy before the report exists.

If footage/annotation cannot be obtained, Phase 1 stops at the baseline and the project must report objective 2 as partial. No synthetic or cherry-picked metrics.

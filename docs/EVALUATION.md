# Evaluation Report (Live Document)

**Status:** not yet complete. This file defines the required evidence and current gaps. Do not cite unfinished rows as results.

**Procedure and gates:** [`VISION.md`](VISION.md#10-evaluation-protocol)
**Current baseline:** [`AUDIT_REPORT.md`](AUDIT_REPORT.md)
**Phase 0 verification:** [`PHASE0_VERIFICATION.md`](PHASE0_VERIFICATION.md)

---

## 1. Vehicle detection and counting

| Metric | Target | Current status | Evidence |
|---|---|---|---|
| mAP50 (overall) | ≥ 0.60 | **not measured** | no annotations/eval script yet |
| mAP50-95 (overall) | ≥ 0.35 | **not measured** | |
| Auto-rickshaw AP50 | ≥ 0.50 | **not measured** | stock COCO has no auto class |
| Per-class precision/recall/F1 | published | **not measured** | |
| Count MAE per clip | ≤ 15% | **not measured** | tracker still custom IoU / concurrent route-gate changes |
| IDF1 / MOTA | IDF1 ≥ 0.60 | **not measured** | |
| Stock COCO baseline | reported | partial: ~38% manual frame recall (14 frames) | [`AUDIT_REPORT.md`](AUDIT_REPORT.md) |

**Known caveat:** the provided sample clips are Seville, Spain and North-East India, not verified Bengaluru CCTV. No detection accuracy claim is valid until a labelled Indian-traffic set is evaluated.

---

## 2. Speed, density, incidents

| Metric | Target | Current status | Evidence |
|---|---|---|---|
| Calibrated speed MAE | ≤ 8 km/h vs GPS/radar | **not measured** | calibration path exists but is not wired to HTTP jobs |
| Occupancy/density MAE | ≤ 5 percentage points | **not measured** | bbox/ROI heuristic; physical density not implemented |
| Incident precision | ≥ 0.70 | **not measured** | heuristic; 962 events/120s in committed artifact |
| Incident recall | ≥ 0.60 | **not measured** | no incident labels |
| PCU/flow validity | window ≥ 5 min or labelled sample estimate | partial (labelled) | UI says “short-clip estimate” |

**Rule:** uncalibrated speed/density is displayed as proxy/requires calibration and must not be used for prediction, signal timing, or route decisions.

---

## 3. Congestion prediction

| Metric | Value | Status |
|---|---|---|
| Holdout accuracy (chronological) | 86.98% | reproducible from committed artifacts |
| Weighted F1 | 87.20% | reproducible |
| Macro F1 | 83.54% | reproducible |
| High-class F1 | 68.92% | weak minority class |
| Majority baseline | 48.23% | measured in audit |
| Persistence baseline | 70.68% | measured in audit |
| `(road, hour, current LOS)` lookup | 86.76% | measured in audit |
| ECE / calibration | not yet published | audit found monotone confidence; formal ECE pending |
| Dataset provenance | **synthetic** 57,600-row benchmark | must be stated with every accuracy claim |

**Rule:** 86.98% must not be presented without the synthetic-data caveat and the lookup baseline. Do not call the benchmark real Kaggle observations.

---

## 4. Signal and route recommendations

| Check | Current status |
|---|---|
| Webster formula unit tests | passing |
| Inputs traceable to measured flow | **not yet** — CV advisory still uses heuristic occupancy→volume; dispatch uses hardcoded road volumes |
| Route geometry real road path | **not yet** — simplified corridor sequence |
| Advisory/non-actuation disclaimer | present in UI/API |

---

## 5. Dashboard/system performance

| Metric | Target | Current status |
|---|---|---|
| Page load (local, 1280×720 / 1920×1080) | < 2s | not formally benchmarked; Phase 0 Playwright smoke passed |
| API p95 | < 300ms local | not formally benchmarked |
| CV processing throughput | report | observed ~28–38 fps on MPS 720p sample; not a formal benchmark |
| Console errors | zero | Phase 0: zero on login/dashboard/nav smoke |
| Horizontal scroll | none 1280–1920 | Phase 0 verified |

A repeatable benchmark script and committed results are Phase 3/4 deliverables.

---

## 6. How to add results

1. Add the dataset/annotation provenance and licence.
2. Run the committed evaluation script with a fixed seed and video-level split.
3. Commit raw JSON + a human-readable table.
4. Update this file and the UI evaluation page.
5. If a gate is not met, mark the objective **partial** and do not claim completion.

No result may be copied from a stale CSV (`Dataset/traffic_prediction_results.csv`, `congestion_comparison.csv`) or from the audit snapshot without re-running the current pipeline.

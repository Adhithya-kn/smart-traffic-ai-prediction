# Traffic System Artifacts & Model Registries (v2.0)

This directory contains trained machine learning artifacts, network topology graphs, operational data ledgers, and secure state storage for the Smart Traffic AI platform.

## 1. Machine Learning & Inference Artifacts (Version 2.0)

| Artifact Name | Format | Primary Role | Provenance & Validation |
| :--- | :--- | :--- | :--- |
| `xgboost_model.joblib` | Scikit-learn / XGBoost binary | Primary production gradient boosting model | Trained on 80-day chronological split (Days 1–80) using 57,600 historical records |
| `model_trees.json` | JSON Tree Representation | Dependency-free pure-Python inference | 80 decision trees evaluated directly in Python without C++ shared library requirements |
| `preprocessor.joblib` | Scikit-learn Pipeline | Feature scaling & one-hot encoding | Standardizes numerical features (Volume, Speed, Hour, Day) and corridor categories |
| `label_encoder.joblib` | Joblib Encapsulation | Target classification encoding | Maps classes: `0: low`, `1: moderate`, `2: high`, `3: severe` |
| `training_metrics.json` | JSON Schema | Empirically verified performance metrics | Records 86.98% out-of-time chronological test accuracy, macro F1 0.8696, and confusion matrix |
| `network_topology.json` | JSON Graph Structure | Spatial graph of Bengaluru corridors | Defines 24 arterial corridors across 8 municipal zones with connectivity, distances, and capacities |

## 2. Operational Ledgers & POSIX Security Hardening

The following state files contain active operational data and are strictly protected with POSIX `0600` (`-rw-------`) file permissions. File operations enforce two-phase atomic write semantics via `atomic_json_dump()` (`.tmp.PID` staging $\to$ `os.fsync()` $\to$ `os.replace()`):

| File | Content & Purpose | Security Controls |
| :--- | :--- | :--- |
| `users.json` | User accounts, roles (`commuter`, `traffic_authority`), salted PBKDF2-HMAC-SHA256 password hashes | Stored verifiers with 100,000 PBKDF2 iterations; strict `0600` mode |
| `sessions.json` | Active bearer authentication tokens, user associations, and ISO-8601 expiry timestamps | Auto-expired on logout/timeout; strict `0600` mode |
| `events.json` | Published municipal road incidents, metro construction zones, and tactical bypass routes | Validated corridor coordinate catchment; strict `0600` mode |
| `vision_jobs.json` | Edge video processing queues, detection counts, average speeds, and status metadata | User-isolated ownership enforcement; strict `0600` mode |
| `.secrets.vault` | Local encrypted credential container | Restrictive permissions; excluded from public archives |

## 3. Backup Retention & Access Controls

- Directory: `traffic_system/artifacts/backups/`
- All snapshots are generated with secret masking (passwords, salts, and tokens are scrubbed prior to serialization).
- Rolling retention policy enforces a maximum snapshot ceiling (default: 5 versions) to eliminate disk exhaustion.
- Directory contains `.gitkeep` to preserve structure in git while individual snapshots are excluded via `.gitignore`.

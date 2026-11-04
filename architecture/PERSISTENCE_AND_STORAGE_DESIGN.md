# Production Persistence & Durability Architecture Design

## 1. Executive Summary & Durability Invariants
This document outlines the data lifecycle, storage tiering, schema migrations, and backup/restore specifications for the Smart Traffic AI platform across local prototype, cloud container (Render/Docker), and serverless (Vercel) execution environments.

### Core Persistence Invariants
1. **POSIX Two-Phase Atomic Commit**:
   All database writes (`users.json`, `sessions.json`, `events.json`, `incident_history.json`, `vision_jobs.json`) execute via POSIX two-phase commit:
   - Data is dumped to an isolated temporary file (`atomic_json_*.tmp`) on the same filesystem.
   - Hardware cache synchronization is forced via `fcntl.fcntl(fileno, fcntl.F_FULLFSYNC)` (macOS) or `os.fsync(fileno)` (Linux).
   - Atomic replacement is performed via `os.replace`, guaranteeing readers never encounter partial or corrupted JSON payloads.
2. **Per-Path Cross-Thread Synchronization**:
   `atomic_json_dump` enforces per-canonical-path mutex locking to serialize concurrent writes to identical records, eliminating race conditions.
3. **Zero Plaintext Secrets**:
   Third-party API keys and master tokens are encrypted in volatile RAM and stored in `.secrets.vault` using AES-256-GCM authenticated encryption; they are never dumped into ordinary JSON files.

---

## 2. Record Classification & Storage Tiering

| Data Entity | Persistence Path | Tier / Durability | Retention Policy | Recovery Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **User Accounts** | `users.json` | Persistent Tier | Permanent | Snapshot restore / DB backup |
| **Active Sessions** | `sessions.json` | Persistent Tier | 24 Hours TTL | Auto-pruning on expiry |
| **Municipal Events** | `events.json` | Persistent Tier | Active dates | Dynamic daily alignment |
| **Incident History** | `incident_history.json` | Persistent Tier | Permanent | Append-only archival |
| **Vision Job Metadata**| `vision_jobs.json` | Persistent Tier | 7 Days | Interrupted marked FAILED |
| **Raw & Annotated Video**| `storage/videos/` | Persistent Object/File | 7 Days / 5GB Cap | Auto-pruned at 85% cap |
| **Snapshots & Backups**| `artifacts/backups/`| Cold Storage Tier | Permanent | SHA-256 integrity checked |
| **Telemetry Caches** | In-Memory volatile | Ephemeral Tier | 60s TTL | Re-queried or baseline |
| **Rate Limit Buckets**| In-Memory volatile | Ephemeral Tier | 60s Window | Auto-refilled via clock |

---

## 3. Production Cloud Storage vs. Local Prototype

### Local Prototype / Demonstration Mode
- Storage is rooted in `traffic_system/artifacts/` and `traffic_system/storage/videos/`.
- Local disk guarantees durability across server restarts on macOS, Linux, and Windows development machines.

### Render Cloud Deployment
- **Free Tier Constraint**: Free Render web services use an ephemeral container filesystem. Data written to `/app` is erased whenever the instance spins down after inactivity or during redeployments.
- **Production Solution**: Upgrade to Render Starter ($7/mo) and attach a Persistent Disk:
  ```yaml
  services:
    - type: web
      name: smart-traffic-ai-backend
      plan: starter
      disk:
        name: smart-traffic-data
        mountPath: /var/data
        sizeGB: 10
      envVars:
        - key: PERSISTENT_DATA_DIR
          value: /var/data
  ```
- `traffic_system/config.py` detects `PERSISTENT_DATA_DIR` and automatically anchors `artifacts/`, `storage/videos/`, and databases inside the persistent disk mount.

### Vercel Serverless Deployment
- Vercel functions execute in read-only sandbox environments with only `/tmp` writable.
- In `traffic_system/config.py`, `IS_VERCEL` routes runtime DBs to `/tmp/traffic_system`.
- In enterprise production on Vercel, replace local `/tmp` files with managed cloud services:
  - **Relational DB**: Neon / Supabase Serverless Postgres (for users, sessions, events).
  - **Object Storage**: AWS S3 / Cloudflare R2 / Google Cloud Storage (for raw MP4 uploads and annotated computer vision videos).

---

## 4. Backup, Restoration & Integrity Verification

### Snapshot Backups (`StorageSynthesizer`)
1. Generates atomic snapshot records combining `users`, `sessions`, `events`, `incident_history`, and `jobs`.
2. Computes SHA-256 cryptographic checksums across the normalized JSON payload.
3. Writes snapshot to `traffic_system/artifacts/backups/snapshot_YYYYMMDD_HHMMSS.json`.

### Zero-Data-Loss Restoration
1. Validates file path containment to prevent path traversal escapes.
2. Recalculates SHA-256 hash and verifies against the snapshot manifest.
3. Restores individual database files using two-phase atomic write.
4. Hot-reloads in-memory singletons (`SecurityManager`, `EventManager`, `VisionJobManager`).

---

## 5. Schema Migration Framework (`migrations.py`)
- Standardizes records to `CURRENT_SCHEMA_VERSION = 2`.
- Automatic migration hooks execute during `_load_users()`, `_load_sessions()`, `_load_events()`, and `_load_persisted_jobs()`.
- Guarantees backward compatibility with legacy student prototype JSON files while adding modern audit attributes (`is_active`, `schema_version`, `created_at`, `archived_at`).

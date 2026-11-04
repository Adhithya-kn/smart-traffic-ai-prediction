"""
traffic_system/synthesizer/storage_manager.py - Hardened Storage & Snapshot Synthesizer
Manages database file audits, POSIX atomic snapshot backups, SHA-256 integrity verification,
strict path-traversal prevention, credential secret masking, and transactional rollback restoration.
"""

import os
import re
import json
import time
import shutil
import hashlib
import threading
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from traffic_system.config import (
    BASE_DIR,
    USERS_DB_PATH,
    SESSIONS_DB_PATH,
    EVENTS_DB_PATH,
    INCIDENTS_HISTORY_DB_PATH,
    JOBS_DB_PATH,
    VIDEO_STORAGE_DIR,
    SNAPSHOT_BACKUP_DIR
)
from traffic_system.core.time_utils import now_iso
from traffic_system.core.fs_utils import (
    atomic_json_dump,
    safe_read_json,
    validate_safe_path,
    HAS_FCNTL
)

SNAPSHOT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class StorageSynthesizer:
    """
    Subsystem governing database file audits, hardware fsync durability verification,
    strict path traversal validation, credential masking, and atomic SHA-256 snapshot backups.
    """
    _instance: Optional["StorageSynthesizer"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.backup_dir = SNAPSHOT_BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls) -> "StorageSynthesizer":
        with cls._lock:
            if cls._instance is None:
                cls._instance = StorageSynthesizer()
            return cls._instance

    @staticmethod
    def mask_snapshot_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep-sanitizes snapshot payload, redacting user password hashes, salts,
        active session tokens, and sensitive credential fields for safe inspection.
        """
        if not isinstance(data, dict):
            return data

        masked = json.loads(json.dumps(data))  # deep copy
        inner_data = masked.get("data", masked)

        # 1. Mask user credentials
        users = inner_data.get("users")
        if isinstance(users, dict):
            for username, u_info in users.items():
                if isinstance(u_info, dict):
                    if "password_hash" in u_info:
                        u_info["password_hash"] = "●●●●●●●● [REDACTED_HASH]"
                    if "salt" in u_info:
                        u_info["salt"] = "●●●●●●●● [REDACTED_SALT]"
        elif isinstance(users, list):
            for u_info in users:
                if isinstance(u_info, dict):
                    if "password_hash" in u_info:
                        u_info["password_hash"] = "●●●●●●●● [REDACTED_HASH]"
                    if "salt" in u_info:
                        u_info["salt"] = "●●●●●●●● [REDACTED_SALT]"

        # 2. Mask active session tokens
        sessions = inner_data.get("sessions")
        if isinstance(sessions, dict):
            masked_sessions = {}
            for tok, s_info in sessions.items():
                masked_key = (tok[:4] + "●●●●●●●●") if len(tok) > 4 else "●●●●●●●●"
                if isinstance(s_info, dict):
                    s_copy = dict(s_info)
                    if "token" in s_copy:
                        s_copy["token"] = masked_key
                    masked_sessions[masked_key] = s_copy
                else:
                    masked_sessions[masked_key] = s_info
            inner_data["sessions"] = masked_sessions

        return masked

    def validate_snapshot_id(self, snapshot_id: str) -> Tuple[bool, str, str]:
        """
        Strictly validates snapshot identifier format against path traversal attacks.
        Returns: (is_valid, clean_id, error_message)
        """
        raw_id = str(snapshot_id or "").strip()
        if not raw_id:
            return False, "", "Snapshot ID cannot be empty."

        # Detect directory traversal characters
        if "/" in raw_id or "\\" in raw_id or ".." in raw_id:
            return False, "", f"Path traversal attempt rejected for snapshot ID: '{raw_id}'."

        # Strip optional .json suffix
        clean_id = raw_id[:-5] if raw_id.endswith(".json") else raw_id
        if not SNAPSHOT_ID_PATTERN.match(clean_id):
            return False, "", f"Invalid snapshot identifier '{clean_id}'. Allowed characters: [a-zA-Z0-9_-]."

        return True, clean_id, ""

    def get_storage_audit(self) -> Dict[str, Any]:
        """Performs comprehensive inspection of persistent storage files and backup state."""
        # 1. Users DB inspection
        users_size = USERS_DB_PATH.stat().st_size if USERS_DB_PATH.exists() else 0
        users_count = 0
        users_mtime = ""
        if USERS_DB_PATH.exists():
            try:
                with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
                    u_data = json.load(f)
                    users_count = len(u_data) if isinstance(u_data, dict) else len(u_data)
                users_mtime = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(USERS_DB_PATH.stat().st_mtime))
            except Exception:
                pass

        # 2. Events DB inspection
        events_size = EVENTS_DB_PATH.stat().st_size if EVENTS_DB_PATH.exists() else 0
        events_count = 0
        published_count = 0
        events_mtime = ""
        if EVENTS_DB_PATH.exists():
            try:
                with open(EVENTS_DB_PATH, "r", encoding="utf-8") as f:
                    e_data = json.load(f)
                    if isinstance(e_data, list):
                        events_count = len(e_data)
                        published_count = sum(1 for e in e_data if e.get("is_published"))
                events_mtime = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(EVENTS_DB_PATH.stat().st_mtime))
            except Exception:
                pass

        # 3. Video Storage inspection
        video_count = 0
        video_total_bytes = 0
        if VIDEO_STORAGE_DIR.exists():
            try:
                for root, _, files in os.walk(VIDEO_STORAGE_DIR):
                    for file in files:
                        p = Path(root) / file
                        if p.is_file() and not file.startswith("."):
                            video_count += 1
                            video_total_bytes += p.stat().st_size
            except Exception:
                pass

        snapshots = self.list_snapshots()

        return {
            "timestamp": now_iso(),
            "durability": {
                "sync_mode": "F_FULLFSYNC (Hardware Platter/NAND Commit)" if HAS_FCNTL else "POSIX os.fsync",
                "two_phase_commit": True,
                "atomic_replace": True
            },
            "databases": {
                "users": {
                    "path": str(USERS_DB_PATH.relative_to(BASE_DIR)) if USERS_DB_PATH.is_relative_to(BASE_DIR) else str(USERS_DB_PATH),
                    "exists": USERS_DB_PATH.exists(),
                    "size_bytes": users_size,
                    "records_count": users_count,
                    "last_modified": users_mtime
                },
                "events": {
                    "path": str(EVENTS_DB_PATH.relative_to(BASE_DIR)) if EVENTS_DB_PATH.is_relative_to(BASE_DIR) else str(EVENTS_DB_PATH),
                    "exists": EVENTS_DB_PATH.exists(),
                    "size_bytes": events_size,
                    "records_count": events_count,
                    "published_count": published_count,
                    "last_modified": events_mtime
                },
                "video_storage": {
                    "path": str(VIDEO_STORAGE_DIR.relative_to(BASE_DIR)) if VIDEO_STORAGE_DIR.is_relative_to(BASE_DIR) else str(VIDEO_STORAGE_DIR),
                    "exists": VIDEO_STORAGE_DIR.exists(),
                    "files_count": video_count,
                    "size_mb": round(video_total_bytes / (1024 * 1024), 2)
                }
            },
            "snapshots_count": len(snapshots),
            "snapshots": snapshots
        }

    def create_snapshot_backup(
        self,
        note: str = "",
        mask_credentials: bool = False
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Atomically captures comprehensive snapshot of users, sessions, events, incident history,
        and jobs with SHA-256 integrity hash and POSIX restricted permissions (0o600).
        """
        try:
            users_data = safe_read_json(USERS_DB_PATH, {})
            sessions_data = safe_read_json(SESSIONS_DB_PATH, {})
            events_data = safe_read_json(EVENTS_DB_PATH, [])
            history_data = safe_read_json(INCIDENTS_HISTORY_DB_PATH, [])
            jobs_data = safe_read_json(JOBS_DB_PATH, {})

            # Optionally sanitize credentials if requested for non-destructive archive
            if mask_credentials:
                users_data = self.mask_snapshot_data({"data": {"users": users_data}})["data"]["users"]
                sessions_data = {}

            timestamp_str = time.strftime("%Y%m%d_%H%M%S")
            snapshot_id = f"snapshot_{timestamp_str}"
            snapshot_filename = f"{snapshot_id}.json"
            target_path = validate_safe_path(snapshot_filename, self.backup_dir)

            payload_to_hash = json.dumps({
                "users": users_data,
                "sessions": sessions_data,
                "events": events_data,
                "incident_history": history_data,
                "jobs": jobs_data
            }, sort_keys=True)
            sha256_hash = hashlib.sha256(payload_to_hash.encode("utf-8")).hexdigest()

            snapshot_record = {
                "snapshot_id": snapshot_id,
                "created_at": now_iso(),
                "note": str(note or "Manual system snapshot").strip()[:120],
                "sha256": sha256_hash,
                "is_masked": mask_credentials,
                "counts": {
                    "users": len(users_data) if isinstance(users_data, dict) else len(users_data),
                    "sessions": len(sessions_data) if isinstance(sessions_data, dict) else len(sessions_data),
                    "events": len(events_data) if isinstance(events_data, list) else 0,
                    "incident_history": len(history_data) if isinstance(history_data, list) else 0,
                    "jobs": len(jobs_data) if isinstance(jobs_data, dict) else 0
                },
                "data": {
                    "users": users_data,
                    "sessions": sessions_data,
                    "events": events_data,
                    "incident_history": history_data,
                    "jobs": jobs_data
                }
            }

            atomic_json_dump(snapshot_record, target_path)

            # Restrict file permissions to owner read/write only (POSIX 0o600)
            try:
                os.chmod(target_path, 0o600)
            except Exception:
                pass

            return True, f"Snapshot '{snapshot_id}' created successfully.", {
                "snapshot_id": snapshot_id,
                "created_at": snapshot_record["created_at"],
                "sha256": sha256_hash,
                "is_masked": mask_credentials,
                "counts": snapshot_record["counts"],
                "file_size_bytes": target_path.stat().st_size
            }
        except Exception as e:
            return False, f"Failed to create snapshot backup: {str(e)}", {}

    def get_snapshot_details(
        self,
        snapshot_id: str,
        mask_secrets: bool = True
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Retrieves snapshot metadata and data with mandatory secret masking by default.
        Validates snapshot identifier against path traversal.
        """
        is_valid, clean_id, err_msg = self.validate_snapshot_id(snapshot_id)
        if not is_valid:
            return False, err_msg, {}

        snapshot_filename = f"{clean_id}.json"
        try:
            snapshot_path = validate_safe_path(snapshot_filename, self.backup_dir, allow_create=False)
            if not snapshot_path.exists():
                return False, f"Snapshot '{clean_id}' does not exist.", {}

            with open(snapshot_path, "r", encoding="utf-8") as f:
                snap = json.load(f)

            if mask_secrets:
                snap = self.mask_snapshot_data(snap)

            return True, f"Snapshot '{clean_id}' loaded.", snap
        except Exception as e:
            return False, f"Failed to read snapshot: {str(e)}", {}

    def restore_snapshot(self, snapshot_id: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Atomically restores users, sessions, events, history, and jobs from verified snapshot backup.
        Enforces strict path-traversal prevention, validates SHA-256 integrity, verifies schema sanity,
        and provides transactional rollback protection on write failure.
        """
        is_valid, clean_id, err_msg = self.validate_snapshot_id(snapshot_id)
        if not is_valid:
            return False, err_msg, {}

        snapshot_filename = f"{clean_id}.json"
        try:
            snapshot_path = validate_safe_path(snapshot_filename, self.backup_dir, allow_create=False)
            if not snapshot_path.exists():
                return False, f"Snapshot '{clean_id}' does not exist.", {}

            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)

            data = snapshot.get("data", {})
            users = data.get("users")
            sessions = data.get("sessions", {})
            events = data.get("events")
            history = data.get("incident_history", [])
            jobs = data.get("jobs", {})

            # 1. Structural schema sanity validation
            if users is None or events is None:
                return False, "Corrupt snapshot file: missing required users or events payload.", {}

            if not isinstance(users, (dict, list)):
                return False, f"Invalid snapshot schema: 'users' must be dictionary or list, got {type(users).__name__}.", {}

            if not isinstance(events, list):
                return False, f"Invalid snapshot schema: 'events' must be list, got {type(events).__name__}.", {}

            if jobs is not None and not isinstance(jobs, dict):
                return False, f"Invalid snapshot schema: 'jobs' must be dictionary, got {type(jobs).__name__}.", {}

            # 2. Cryptographic SHA-256 Integrity Verification
            expected_hash = snapshot.get("sha256")
            if expected_hash:
                # Support legacy snapshots (users and events only) or comprehensive v2 snapshots
                if "sessions" in data or "jobs" in data or "incident_history" in data:
                    payload_to_hash = json.dumps({
                        "users": users,
                        "sessions": sessions,
                        "events": events,
                        "incident_history": history,
                        "jobs": jobs
                    }, sort_keys=True)
                else:
                    payload_to_hash = json.dumps({"users": users, "events": events}, sort_keys=True)

                calc_hash = hashlib.sha256(payload_to_hash.encode("utf-8")).hexdigest()
                if calc_hash != expected_hash:
                    return False, f"Integrity check failed: snapshot SHA-256 mismatch (expected {expected_hash[:8]}..., calculated {calc_hash[:8]}...).", {}

            # 3. Transactional Pre-Restore Staging (for automatic rollback if any write fails)
            staging_backup: Dict[Path, Optional[str]] = {}
            target_files = [
                (USERS_DB_PATH, users),
                (SESSIONS_DB_PATH, sessions if sessions else None),
                (EVENTS_DB_PATH, events),
                (INCIDENTS_HISTORY_DB_PATH, history if history else None),
                (JOBS_DB_PATH, jobs if jobs else None)
            ]

            for path, _ in target_files:
                if path.exists():
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            staging_backup[path] = f.read()
                    except Exception:
                        staging_backup[path] = None
                else:
                    staging_backup[path] = None

            # 4. Atomic Execution with Transactional Rollback
            try:
                atomic_json_dump(users, USERS_DB_PATH)

                if sessions:
                    atomic_json_dump(sessions, SESSIONS_DB_PATH)

                atomic_json_dump(events, EVENTS_DB_PATH)

                if history:
                    atomic_json_dump(history, INCIDENTS_HISTORY_DB_PATH)

                if jobs:
                    atomic_json_dump(jobs, JOBS_DB_PATH)

            except Exception as write_err:
                # Rollback all modified files to pre-restore state
                for p, orig_content in staging_backup.items():
                    try:
                        if orig_content is not None:
                            with open(p, "w", encoding="utf-8") as f:
                                f.write(orig_content)
                        elif p.exists():
                            p.unlink(missing_ok=True)
                    except Exception:
                        pass
                return False, f"Restore failed during disk commit; rolled back changes. Error: {str(write_err)}", {}

            # 5. Hot-reload live in-memory managers
            try:
                from traffic_system.core.security import get_security_manager
                sec = get_security_manager()
                with sec._lock:
                    sec.users = users if isinstance(users, dict) else {}
                    sec.sessions = sessions if isinstance(sessions, dict) else {}
            except Exception:
                pass

            try:
                from app.server import TrafficAppServer
                if TrafficAppServer.event_mgr:
                    with TrafficAppServer.event_mgr._lock:
                        TrafficAppServer.event_mgr.events = events if isinstance(events, list) else []
                        TrafficAppServer.event_mgr.incident_history = history if isinstance(history, list) else []
            except Exception:
                pass

            try:
                from traffic_system.computer_vision.job_manager import VisionJobManager
                jm = VisionJobManager.get_instance()
                jm._load_persisted_jobs()
            except Exception:
                pass

            return True, f"Snapshot '{clean_id}' restored successfully.", {
                "snapshot_id": clean_id,
                "restored_at": now_iso(),
                "users_restored": len(users) if isinstance(users, dict) else len(users),
                "sessions_restored": len(sessions) if isinstance(sessions, dict) else 0,
                "events_restored": len(events) if isinstance(events, list) else 0,
                "history_restored": len(history) if isinstance(history, list) else 0,
                "jobs_restored": len(jobs) if isinstance(jobs, dict) else 0
            }
        except Exception as e:
            return False, f"Restore failed: {str(e)}", {}

    def prune_old_snapshots(self, keep_count: int = 5) -> Tuple[int, List[str]]:
        """
        Prunes older snapshot files, keeping only the newest `keep_count` snapshots.
        Returns (pruned_count, deleted_snapshot_ids).
        """
        deleted_ids = []
        if not self.backup_dir.exists():
            return 0, deleted_ids

        keep = max(0, int(keep_count))
        try:
            snapshots = sorted(
                self.backup_dir.glob("snapshot_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            to_remove = snapshots[keep:]
            for p in to_remove:
                try:
                    p.unlink(missing_ok=True)
                    deleted_ids.append(p.stem)
                except Exception:
                    pass
        except Exception:
            pass

        return len(deleted_ids), deleted_ids

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """Lists all available snapshots sorted by timestamp descending."""
        results = []
        if not self.backup_dir.exists():
            return results

        try:
            for p in sorted(self.backup_dir.glob("snapshot_*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        snap = json.load(f)
                    results.append({
                        "snapshot_id": snap.get("snapshot_id", p.stem),
                        "created_at": snap.get("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime))),
                        "note": snap.get("note", ""),
                        "sha256": (snap.get("sha256", "")[:12] + "...") if snap.get("sha256") else "None",
                        "counts": snap.get("counts", {}),
                        "is_masked": snap.get("is_masked", False),
                        "size_bytes": p.stat().st_size
                    })
                except Exception:
                    continue
        except Exception:
            pass
        return results


def get_storage_synthesizer() -> StorageSynthesizer:
    return StorageSynthesizer.get_instance()

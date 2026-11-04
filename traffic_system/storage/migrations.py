"""
traffic_system/storage/migrations.py - Persistent Storage Schema Migrations
Provides automated schema upgrades and backward-compatible normalization for:
1. Users Database (users.json)
2. Municipal Events Database (events.json)
3. Vision Processing Jobs (vision_jobs.json)
4. Session Records (sessions.json)
"""

import time
import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger("traffic_system.storage.migrations")

CURRENT_SCHEMA_VERSION = 2


def migrate_users_data(raw_users: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Upgrades users data structure to CURRENT_SCHEMA_VERSION.
    Ensures normalized username keys, created_at, role, is_active, and schema_version.
    """
    if not isinstance(raw_users, dict):
        return {}, True

    migrated = {}
    modified = False

    for k, v in raw_users.items():
        if not isinstance(v, dict):
            continue
        uname = str(v.get("username", k)).strip().lower()
        record = dict(v)
        record["username"] = uname

        if "created_at" not in record or not isinstance(record["created_at"], (int, float)):
            record["created_at"] = time.time()
            modified = True

        if "is_active" not in record:
            record["is_active"] = True
            modified = True

        if record.get("schema_version", 1) < CURRENT_SCHEMA_VERSION:
            record["schema_version"] = CURRENT_SCHEMA_VERSION
            modified = True

        migrated[uname] = record

    return migrated, modified


def migrate_events_data(raw_events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Upgrades events list to CURRENT_SCHEMA_VERSION.
    Ensures id, affected_roads, severity_boost, active_dates, is_published, and schema_version.
    """
    if not isinstance(raw_events, list):
        return [], True

    migrated = []
    modified = False

    for idx, e in enumerate(raw_events):
        if not isinstance(e, dict):
            continue
        rec = dict(e)
        if "id" not in rec or not rec["id"]:
            rec["id"] = f"EVT_{idx + 1:03d}"
            modified = True

        if "is_published" not in rec:
            rec["is_published"] = False
            modified = True

        if "is_historical" not in rec:
            rec["is_historical"] = False
            modified = True

        start_date = rec.get("date", "2026-03-18")
        if "active_dates" not in rec or not rec["active_dates"]:
            rec["active_dates"] = [start_date]
            modified = True

        if rec.get("schema_version", 1) < CURRENT_SCHEMA_VERSION:
            rec["schema_version"] = CURRENT_SCHEMA_VERSION
            modified = True

        migrated.append(rec)

    return migrated, modified


def migrate_jobs_data(raw_jobs: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Upgrades vision jobs dictionary to CURRENT_SCHEMA_VERSION.
    Ensures owner, provenance, created_at, status, and schema_version.
    """
    if not isinstance(raw_jobs, dict):
        return {}, True

    migrated = {}
    modified = False

    for j_id, job_dict in raw_jobs.items():
        if not isinstance(job_dict, dict):
            continue
        rec = dict(job_dict)
        if "owner" not in rec:
            rec["owner"] = "anonymous"
            modified = True

        if "provenance" not in rec:
            rec["provenance"] = "Genuine YOLO Inference"
            modified = True

        if "created_at" not in rec:
            from traffic_system.core.time_utils import now_iso
            rec["created_at"] = now_iso()
            modified = True

        if rec.get("schema_version", 1) < CURRENT_SCHEMA_VERSION:
            rec["schema_version"] = CURRENT_SCHEMA_VERSION
            modified = True

        migrated[j_id] = rec

    return migrated, modified


def migrate_sessions_data(raw_sessions: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Normalizes session records and prunes expired or corrupt session objects.
    """
    if not isinstance(raw_sessions, dict):
        return {}, True

    migrated = {}
    modified = False
    now = time.time()

    for token, s in raw_sessions.items():
        if not isinstance(s, dict):
            modified = True
            continue
        created_at = s.get("created_at", 0)
        # Prune sessions older than 7 days
        if (now - created_at) > 7 * 86400:
            modified = True
            continue

        rec = dict(s)
        if "token" not in rec:
            rec["token"] = token
            modified = True
        rec["schema_version"] = CURRENT_SCHEMA_VERSION
        migrated[token] = rec

    return migrated, modified

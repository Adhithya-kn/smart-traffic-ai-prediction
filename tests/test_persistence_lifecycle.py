"""
tests/test_persistence_lifecycle.py - End-to-End Tests for Data & Persistent Storage
Validates:
1. User accounts persistence across SecurityManager re-instantiation.
2. Active sessions persistence across restarts with TTL expiration pruning.
3. Events and incident history persistent archival in EventManager.
4. Vision job metadata persistence and server restart interruption recovery.
5. Video file storage, SHA-256 integrity hashing, and verification.
6. Automated retention policies and disk storage capacity cleanup.
7. Snapshot backup creation and verified zero-data-loss restoration with SHA-256 check.
8. Concurrent multi-threaded atomic writes without JSON corruption.
9. Storage schema migrations (v1 legacy to v2 upgraded format).
10. Simulated server restart and redeployment state preservation.
"""

import io
import json
import time
import shutil
import tempfile
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from traffic_system.core.security import SecurityManager, hash_password
from traffic_system.core.entities import UserRole, EventType
from traffic_system.events.event_manager import EventManager
from traffic_system.storage.video_storage import VideoStorage
from traffic_system.computer_vision.job_manager import VisionJobManager
from traffic_system.computer_vision.schemas import JobStatus
from traffic_system.synthesizer.storage_manager import StorageSynthesizer
from traffic_system.core.fs_utils import atomic_json_dump, safe_read_json
from traffic_system.storage.migrations import (
    migrate_users_data,
    migrate_events_data,
    migrate_jobs_data,
    migrate_sessions_data
)


@pytest.fixture
def temp_storage_env(tmp_path):
    """Creates isolated temporary directories for persistence testing."""
    users_db = tmp_path / "users.json"
    sessions_db = tmp_path / "sessions.json"
    events_db = tmp_path / "events.json"
    history_db = tmp_path / "incident_history.json"
    jobs_db = tmp_path / "vision_jobs.json"
    videos_dir = tmp_path / "videos"
    backups_dir = tmp_path / "backups"

    videos_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)

    return {
        "root": tmp_path,
        "users_db": users_db,
        "sessions_db": sessions_db,
        "events_db": events_db,
        "history_db": history_db,
        "jobs_db": jobs_db,
        "videos_dir": videos_dir,
        "backups_dir": backups_dir
    }


# -----------------------------------------------------------------------------
# 1. User Accounts and Sessions Persistence Across Restarts
# -----------------------------------------------------------------------------
def test_users_and_sessions_persistence_across_restarts(temp_storage_env):
    users_db = temp_storage_env["users_db"]
    sessions_db = temp_storage_env["sessions_db"]

    # Initial session 1
    sec1 = SecurityManager(db_path=users_db, sessions_db_path=sessions_db)
    ok, msg = sec1.register("operator_blr", "SecurePass@123", role=UserRole.TRAFFIC_MANAGEMENT.value, is_admin_invoker=True)
    assert ok is True

    login_ok, login_msg, session = sec1.login("operator_blr", "SecurePass@123")
    assert login_ok is True
    token = session["token"]

    # Verify session is valid in instance 1
    assert sec1.get_user_by_token(token) is not None

    # Simulate Server Restart by creating a completely new SecurityManager instance
    sec2 = SecurityManager(db_path=users_db, sessions_db_path=sessions_db)

    # 1. User account persisted
    assert "operator_blr" in sec2.users
    assert sec2.users["operator_blr"]["role"] == UserRole.TRAFFIC_MANAGEMENT.value

    # 2. Active session token persisted and valid
    user_from_tok = sec2.get_user_by_token(token)
    assert user_from_tok is not None
    assert user_from_tok["username"] == "operator_blr"

    # 3. Verify session expiration pruning
    # Manually backdate session creation time to simulate expiry
    with sec2._lock:
        sec2.sessions[token]["created_at"] = time.time() - 90000  # Older than 24h (86400s)
        sec2._save_sessions()

    # Re-instantiate server (instance 3)
    sec3 = SecurityManager(db_path=users_db, sessions_db_path=sessions_db)
    assert sec3.get_user_by_token(token) is None
    assert token not in sec3.sessions


# -----------------------------------------------------------------------------
# 2. Events & Incident History Archival Persistence
# -----------------------------------------------------------------------------
def test_events_and_incident_history_persistence(temp_storage_env):
    events_db = temp_storage_env["events_db"]
    history_db = temp_storage_env["history_db"]

    em1 = EventManager(db_path=events_db, history_db_path=history_db)
    # Add a custom event
    custom_event = {
        "name": "Silk Board Monsoon Waterlog Alert",
        "event_type": EventType.ROADWORK.value,
        "city_zone": "Electronic City South",
        "affected_roads": ["RD_BLR_11"],
        "start_time": "08:00",
        "end_time": "18:00",
        "date": "2026-11-04",
        "severity_boost": 3,
        "volume_surge_vph": 800,
        "capacity_constriction_pct": 50,
        "speed_impact_pct": 60,
        "is_published": True,
        "description": "Culvert overflow at Silk Board loop."
    }
    ok, msg, created_evt = em1.add_event(custom_event)
    assert ok is True
    eid = created_evt["id"]

    # Delete the event to test historical archival
    del_ok, del_msg = em1.delete_event(eid)
    assert del_ok is True
    assert len(em1.incident_history) == 1
    assert em1.incident_history[0]["id"] == eid
    assert em1.incident_history[0]["resolution"] == "DELETED_OR_RESOLVED"

    # Simulate server restart
    em2 = EventManager(db_path=events_db, history_db_path=history_db)
    # Active events no longer contains deleted event
    assert not any(e["id"] == eid for e in em2.events)
    # Incident history preserved across restart
    hist = em2.get_incident_history()
    assert len(hist) == 1
    assert hist[0]["id"] == eid


# -----------------------------------------------------------------------------
# 3. Vision Job Metadata Persistence & Server Restart Interruption Recovery
# -----------------------------------------------------------------------------
def test_vision_job_persistence_and_interruption_recovery(temp_storage_env, monkeypatch):
    jobs_db = temp_storage_env["jobs_db"]
    monkeypatch.setattr("traffic_system.computer_vision.job_manager.JOBS_PERSISTENCE_FILE", jobs_db)

    # Initialize manager and write a job that was in PROCESSING status when server shut down
    jm1 = VisionJobManager(max_workers=1)
    jm1.jobs.clear()

    interrupted_job = {
        "job_id": "job_persist_test_01",
        "video_id": "vid_abc123",
        "original_filename": "traffic.mp4",
        "owner": "operator_blr",
        "status": "PROCESSING",
        "progress_pct": 45.0,
        "created_at": "2026-11-04T00:00:00Z"
    }
    atomic_json_dump({"job_persist_test_01": interrupted_job}, jobs_db)

    # Re-initialize manager simulating server reboot
    jm2 = VisionJobManager(max_workers=1)
    recovered = jm2.get_job("job_persist_test_01")
    assert recovered is not None
    # Interrupted processing jobs must be marked FAILED with restart message
    assert recovered.status == JobStatus.FAILED
    assert "Server restarted during job processing" in recovered.error_message


# -----------------------------------------------------------------------------
# 4. Video Storage, SHA-256 Integrity Verification & Retention Cleanup
# -----------------------------------------------------------------------------
def test_video_storage_integrity_and_retention(temp_storage_env):
    videos_dir = temp_storage_env["videos_dir"]
    storage = VideoStorage(base_dir=videos_dir, max_storage_bytes=10 * 1024 * 1024)  # 10 MB limit

    # Valid MP4 binary header
    fake_mp4_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + b"\x00" * 2000

    ok, msg, meta = storage.save_upload(fake_mp4_bytes, "cam_silk_board.mp4", owner="admin")
    assert ok is True
    video_id = meta["video_id"]
    assert "sha256" in meta

    # Check integrity
    integ_ok, integ_msg = storage.verify_video_integrity(video_id)
    assert integ_ok is True
    assert "Integrity verified" in integ_msg

    # Simulate tampered file
    raw_path = storage.get_raw_video_path(video_id)
    with open(raw_path, "ab") as f:
        f.write(b"TAMPERED_BYTES")

    integ_ok2, integ_msg2 = storage.verify_video_integrity(video_id)
    assert integ_ok2 is False
    assert "checksum mismatch" in integ_msg2

    # Test retention policy enforcement
    removed = storage.enforce_retention_policy(max_usage_ratio=0.0, max_age_seconds=0.0)
    assert removed >= 1


# -----------------------------------------------------------------------------
# 5. Snapshot Backup & Zero-Data-Loss Restoration
# -----------------------------------------------------------------------------
def test_snapshot_backup_and_full_restoration(temp_storage_env, monkeypatch):
    backups_dir = temp_storage_env["backups_dir"]
    users_db = temp_storage_env["users_db"]
    sessions_db = temp_storage_env["sessions_db"]
    events_db = temp_storage_env["events_db"]
    history_db = temp_storage_env["history_db"]
    jobs_db = temp_storage_env["jobs_db"]

    monkeypatch.setattr("traffic_system.synthesizer.storage_manager.SNAPSHOT_BACKUP_DIR", backups_dir)
    monkeypatch.setattr("traffic_system.synthesizer.storage_manager.USERS_DB_PATH", users_db)
    monkeypatch.setattr("traffic_system.synthesizer.storage_manager.SESSIONS_DB_PATH", sessions_db)
    monkeypatch.setattr("traffic_system.synthesizer.storage_manager.EVENTS_DB_PATH", events_db)
    monkeypatch.setattr("traffic_system.synthesizer.storage_manager.INCIDENTS_HISTORY_DB_PATH", history_db)
    monkeypatch.setattr("traffic_system.synthesizer.storage_manager.JOBS_DB_PATH", jobs_db)

    # Populate sample records
    atomic_json_dump({"test_user": {"username": "test_user", "role": "Traffic Management"}}, users_db)
    atomic_json_dump({"test_tok_123": {"token": "test_tok_123", "username": "test_user"}}, sessions_db)
    atomic_json_dump([{"id": "EVT_TEST_99", "name": "Marathahalli Flyover Repair"}], events_db)
    atomic_json_dump([{"id": "EVT_HIST_01", "name": "Resolved Flood"}], history_db)
    atomic_json_dump({"job_001": {"job_id": "job_001", "status": "COMPLETED"}}, jobs_db)

    storage_syn = StorageSynthesizer()
    storage_syn.backup_dir = backups_dir

    # 1. Create snapshot
    ok, msg, snap_data = storage_syn.create_snapshot_backup(note="Automated test snapshot")
    assert ok is True
    snap_id = snap_data["snapshot_id"]
    assert "sha256" in snap_data

    # 2. Corrupt or delete active files
    atomic_json_dump({}, users_db)
    atomic_json_dump([], events_db)

    assert safe_read_json(users_db) == {}
    assert safe_read_json(events_db) == []

    # 3. Restore snapshot
    rest_ok, rest_msg, rest_data = storage_syn.restore_snapshot(snap_id)
    assert rest_ok is True
    assert rest_data["users_restored"] == 1
    assert rest_data["events_restored"] == 1

    # Verify active files are completely restored
    restored_users = safe_read_json(users_db)
    assert "test_user" in restored_users
    restored_events = safe_read_json(events_db)
    assert restored_events[0]["id"] == "EVT_TEST_99"


# -----------------------------------------------------------------------------
# 6. Concurrent Multi-Threaded Atomic Writes Durability
# -----------------------------------------------------------------------------
def test_concurrent_atomic_writes_no_corruption(temp_storage_env):
    target_file = temp_storage_env["root"] / "concurrent_records.json"

    # Write initial payload
    atomic_json_dump({"writes": 0}, target_file)

    def writer_task(worker_id: int):
        for i in range(15):
            data = {"worker": worker_id, "iteration": i, "timestamp": time.time(), "payload": [x for x in range(50)]}
            atomic_json_dump(data, target_file)
            # Concurrently read to ensure no partial reads occur
            read_data = safe_read_json(target_file)
            assert read_data is not None
            assert "worker" in read_data
            assert len(read_data["payload"]) == 50

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(writer_task, i) for i in range(6)]
        for f in futures:
            f.result()  # Ensures all 6 concurrent threads completed without exception

    final_read = safe_read_json(target_file)
    assert final_read is not None
    assert "payload" in final_read


# -----------------------------------------------------------------------------
# 7. Schema Migrations from Legacy v1 to Upgraded v2 Format
# -----------------------------------------------------------------------------
def test_schema_migrations():
    # 1. Users migration
    legacy_users = {
        "legacy_admin": {"username": "legacy_admin", "password_hash": "abc", "salt": "123"}
    }
    migrated_users, was_mod = migrate_users_data(legacy_users)
    assert was_mod is True
    assert migrated_users["legacy_admin"]["is_active"] is True
    assert migrated_users["legacy_admin"]["schema_version"] == 2
    assert "created_at" in migrated_users["legacy_admin"]

    # 2. Events migration
    legacy_events = [
        {"name": "Old Silk Board Roadwork", "date": "2026-03-18"}
    ]
    migrated_events, was_mod_events = migrate_events_data(legacy_events)
    assert was_mod_events is True
    assert migrated_events[0]["id"] == "EVT_001"
    assert migrated_events[0]["schema_version"] == 2
    assert "active_dates" in migrated_events[0]

    # 3. Jobs migration
    legacy_jobs = {
        "job_99": {"job_id": "job_99", "status": "COMPLETED"}
    }
    migrated_jobs, was_mod_jobs = migrate_jobs_data(legacy_jobs)
    assert was_mod_jobs is True
    assert migrated_jobs["job_99"]["owner"] == "anonymous"
    assert migrated_jobs["job_99"]["schema_version"] == 2

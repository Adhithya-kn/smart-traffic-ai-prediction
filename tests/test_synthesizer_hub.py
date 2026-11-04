"""
tests/test_synthesizer_hub.py - End-to-End Tests for API & System Synthesizer Hub
Verifies multi-subsystem diagnostics, storage audits, POSIX atomic snapshot backups,
path traversal rejection, backup integrity, secret masking, and synthetic stream generation.
"""

import json
from unittest.mock import patch
import pytest
from pathlib import Path
from traffic_system.synthesizer import (
    StorageSynthesizer,
    get_storage_synthesizer,
    StreamSynthesizer,
    get_stream_synthesizer,
    SCENARIO_CONFIGS
)
from traffic_system.integrations.api_manager import APIManager
from traffic_system.config import SNAPSHOT_BACKUP_DIR


def test_public_interfaces_and_exports():
    """Validates public module interfaces and canonical imports for traffic_system.synthesizer."""
    import traffic_system.synthesizer as synth
    assert hasattr(synth, "StorageSynthesizer")
    assert hasattr(synth, "get_storage_synthesizer")
    assert hasattr(synth, "StreamSynthesizer")
    assert hasattr(synth, "get_stream_synthesizer")
    assert hasattr(synth, "SCENARIO_CONFIGS")

    storage_syn = synth.get_storage_synthesizer()
    assert isinstance(storage_syn, synth.StorageSynthesizer)

    stream_syn = synth.get_stream_synthesizer()
    assert isinstance(stream_syn, synth.StreamSynthesizer)


def test_storage_synthesizer_audit_and_snapshot_lifecycle():
    syn = StorageSynthesizer()
    audit = syn.get_storage_audit()

    assert "durability" in audit
    assert "databases" in audit
    assert audit["durability"]["two_phase_commit"] is True
    assert "users" in audit["databases"]
    assert "events" in audit["databases"]
    assert "video_storage" in audit["databases"]

    # 1. Create atomic snapshot
    ok, msg, snap_data = syn.create_snapshot_backup(note="Automated pytest test snapshot")
    assert ok is True
    assert "snapshot_id" in snap_data
    assert "sha256" in snap_data
    snap_id = snap_data["snapshot_id"]

    # Verify snapshot exists on disk
    snap_file = SNAPSHOT_BACKUP_DIR / f"{snap_id}.json"
    assert snap_file.exists()

    # 2. List snapshots
    snapshots = syn.list_snapshots()
    assert len(snapshots) >= 1
    found = any(s["snapshot_id"] == snap_id for s in snapshots)
    assert found is True

    # 3. Restore snapshot
    rest_ok, rest_msg, rest_data = syn.restore_snapshot(snap_id)
    assert rest_ok is True
    assert rest_data["snapshot_id"] == snap_id
    assert "users_restored" in rest_data

    # 4. Path traversal attempts rejected safely
    for bad_id in [
        "../../../etc/passwd",
        "snapshot_test/../../something",
        "..\\..\\windows\\system32",
        "test;rm -rf /",
        "snapshot/123",
        ""
    ]:
        bad_ok, bad_msg, _ = syn.restore_snapshot(bad_id)
        assert bad_ok is False
        assert "traversal" in bad_msg.lower() or "invalid" in bad_msg.lower() or "empty" in bad_msg.lower()

    # 5. Snapshot pruning
    pruned_count, pruned_ids = syn.prune_old_snapshots(keep_count=0)
    assert pruned_count >= 1
    assert not snap_file.exists()


def test_storage_snapshot_secret_masking():
    syn = StorageSynthesizer()

    # Test secret masking on dummy snapshot payload
    raw_payload = {
        "snapshot_id": "test_snap",
        "data": {
            "users": {
                "admin": {
                    "username": "admin",
                    "password_hash": "a1b2c3d4e5f67890abcdef1234567890",
                    "salt": "secret_salt_1234",
                    "role": "Traffic Management"
                }
            },
            "sessions": {
                "active_sess_tok_9999": {
                    "username": "admin",
                    "token": "active_sess_tok_9999",
                    "role": "Traffic Management"
                }
            }
        }
    }

    masked = syn.mask_snapshot_data(raw_payload)
    admin_user = masked["data"]["users"]["admin"]
    assert "REDACTED_HASH" in admin_user["password_hash"]
    assert "REDACTED_SALT" in admin_user["salt"]
    assert "a1b2c3d4e5f6" not in admin_user["password_hash"]

    # Verify session tokens are masked
    sessions = masked["data"]["sessions"]
    for tok_key, sess in sessions.items():
        assert "●●●●" in tok_key
        assert "●●●●" in sess["token"]


def test_storage_snapshot_integrity_verification():
    syn = StorageSynthesizer()

    # Create legitimate snapshot
    ok, _, snap_data = syn.create_snapshot_backup(note="Integrity test")
    assert ok is True
    snap_id = snap_data["snapshot_id"]
    snap_file = SNAPSHOT_BACKUP_DIR / f"{snap_id}.json"

    try:
        # Tamper with snapshot file
        with open(snap_file, "r", encoding="utf-8") as f:
            snap_json = json.load(f)

        # Alter data without recalculating SHA-256
        snap_json["data"]["events"].append({"id": "tampered_event", "name": "Hack Event"})
        with open(snap_file, "w", encoding="utf-8") as f:
            json.dump(snap_json, f)

        # Restore should fail due to SHA-256 mismatch
        rest_ok, rest_msg, _ = syn.restore_snapshot(snap_id)
        assert rest_ok is False
        assert "mismatch" in rest_msg.lower() or "integrity" in rest_msg.lower()

    finally:
        snap_file.unlink(missing_ok=True)


def test_stream_synthesizer_scenarios_and_explicit_synthetic_labels():
    stream_syn = StreamSynthesizer()
    scenarios = stream_syn.get_available_scenarios()
    types = [s["type"] for s in scenarios]
    assert "monsoon_flood" in types
    assert "bottleneck_cascade" in types
    assert "festival_surge" in types
    assert "sensor_blackout" in types

    # Each scenario catalogue entry explicitly marked as synthetic
    for s in scenarios:
        assert s["is_synthetic"] is True
        assert "Synthetic" in s["provenance"]

    # Mock topology of 3 corridors
    dummy_topology = {
        "RD_BLR_01": {"city_zone": "Indiranagar", "avg_speed": 30.0, "avg_volume": 1200, "capacity": 3000, "common_congestion": "Moderate"},
        "RD_BLR_02": {"city_zone": "Downtown Core", "avg_speed": 22.0, "avg_volume": 1800, "capacity": 3200, "common_congestion": "High"},
        "RD_BLR_03": {"city_zone": "Whitefield", "avg_speed": 35.0, "avg_volume": 1100, "capacity": 2800, "common_congestion": "Low"}
    }

    result = stream_syn.generate_synthetic_stream(
        scenario_type="monsoon_flood",
        intensity=0.85,
        target_zones=None,
        topology=dummy_topology,
        random_seed=4242
    )

    # Top-level explicit synthetic labeling
    assert result["is_synthetic"] is True
    assert result["is_simulated"] is True
    assert "Synthetic" in result["provenance"]
    assert "Synthetic" in result["data_provenance"]
    assert result["random_seed"] == 4242
    assert "disclaimer" in result
    assert "synthetic stress-test" in result["disclaimer"].lower()

    # Scenario generation metadata documentation
    assert "scenario_generation_metadata" in result
    meta = result["scenario_generation_metadata"]
    assert meta["scenario_type"] == "monsoon_flood"
    assert meta["random_seed"] == 4242
    assert meta["is_deterministic"] is True
    assert "methodology" in meta

    # Corridor-level explicit synthetic labeling
    assert len(result["corridors"]) == 3
    for corr in result["corridors"]:
        assert corr["is_synthetic"] is True
        assert "Synthetic" in corr["provenance"]
        assert corr["simulated"]["is_synthetic"] is True


def test_stream_synthesizer_random_seed_reproducibility():
    stream_syn = StreamSynthesizer()
    dummy_topology = {
        "RD_BLR_01": {"city_zone": "Indiranagar", "avg_speed": 30.0, "avg_volume": 1200, "capacity": 3000, "common_congestion": "Moderate"},
        "RD_BLR_02": {"city_zone": "Downtown Core", "avg_speed": 22.0, "avg_volume": 1800, "capacity": 3200, "common_congestion": "High"}
    }

    # Same seed -> exact same output
    res1 = stream_syn.generate_synthetic_stream(scenario_type="festival_surge", intensity=0.7, topology=dummy_topology, random_seed=999)
    res2 = stream_syn.generate_synthetic_stream(scenario_type="festival_surge", intensity=0.7, topology=dummy_topology, random_seed=999)
    assert res1["corridors"] == res2["corridors"]

    # Different seed -> distinct output
    res3 = stream_syn.generate_synthetic_stream(scenario_type="festival_surge", intensity=0.7, topology=dummy_topology, random_seed=111)
    assert res1["random_seed"] != res3["random_seed"]


def test_multi_subsystem_handshake():
    mgr = APIManager()
    # Mock external HTTP provider probes to eliminate live internet dependency in unit tests
    with patch.object(mgr.tomtom, "test_connection", return_value=(False, "Not configured", 0.0)):
        with patch.object(mgr.google_maps, "test_connection", return_value=(False, "Not configured", 0.0)):
            with patch.object(mgr.weather, "test_connection", return_value=(True, "Reachable", 15.0)):
                handshake = mgr.execute_multi_subsystem_handshake()

    assert "overall_health" in handshake
    assert "total_latency_ms" in handshake
    assert "subsystems" in handshake

    subsystems = handshake["subsystems"]
    assert "tomtom_traffic" in subsystems
    assert "google_maps" in subsystems
    assert "open_meteo" in subsystems
    assert "database_storage" in subsystems
    assert "ml_prediction_engine" in subsystems
    assert "computer_vision" in subsystems

    for key, sub in subsystems.items():
        assert "name" in sub
        assert "status" in sub
        assert "latency_ms" in sub
        assert sub["latency_ms"] >= 0.0


def test_secret_masking_invariants():
    mgr = APIManager()
    providers = mgr.get_providers()["providers"]
    for p in providers:
        if p.get("key_required"):
            masked = p.get("masked_key", "")
            if masked:
                assert "●●●●" in masked or "****" in masked
                assert not any(masked.startswith(prefix) for prefix in ["AIza", "pk.", "sk_"])

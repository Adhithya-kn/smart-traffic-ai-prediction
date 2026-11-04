"""
tests/test_video_upload.py - Unit Tests for Video Upload, File Signatures, and Persistence
"""

import time
import pytest
from pathlib import Path
from traffic_system.storage.video_storage import VideoStorage, validate_video_signature


def test_video_upload_successful(tmp_path):
    storage = VideoStorage(base_dir=tmp_path)
    sample_mp4_bytes = b"\x00\x00\x00 ftypisom\x00\x00\x02\x00" + (b"0" * 1024)

    ok, msg, meta = storage.save_upload(sample_mp4_bytes, "traffic_sample.mp4")
    assert ok is True
    assert "video_id" in meta
    assert meta["extension"] == ".mp4"
    assert meta["size_bytes"] == len(sample_mp4_bytes)

    resolved = storage.get_raw_video_path(meta["video_id"])
    assert resolved is not None
    assert resolved.exists()
    assert resolved.read_bytes() == sample_mp4_bytes


def test_video_upload_disallowed_extension(tmp_path):
    storage = VideoStorage(base_dir=tmp_path)
    payload = b"\x00\x00\x00 ftypisom" + b"test script"
    ok, msg, _ = storage.save_upload(payload, "malicious_script.sh")
    assert ok is False
    assert "Unsupported file extension" in msg


def test_video_upload_size_limit(tmp_path, monkeypatch):
    storage = VideoStorage(base_dir=tmp_path)
    # Monkeypatch max upload size to 1000 bytes
    import traffic_system.storage.video_storage as vs_mod
    monkeypatch.setattr(vs_mod, "MAX_VIDEO_UPLOAD_SIZE", 1000)

    large_payload = b"\x00\x00\x00 ftypisom" + (b"x" * 1001)
    ok, msg, _ = storage.save_upload(large_payload, "large_sample.mp4")
    assert ok is False
    assert "exceeds limit" in msg


def test_video_upload_path_traversal_sanitization(tmp_path):
    storage = VideoStorage(base_dir=tmp_path)
    sample_bytes = b"\x00\x00\x00\x18ftypmp42" + b"safe content"
    ok, msg, meta = storage.save_upload(sample_bytes, "../../../etc/cron.d/hack.mp4")
    assert ok is True
    saved_path = Path(meta["file_path"])
    # Confirms it is strictly contained inside the tmp_path uploads folder
    assert saved_path.parent == storage.raw_dir
    assert ".." not in saved_path.name


def test_video_signature_validation():
    # Valid MP4 signatures
    assert validate_video_signature(b"\x00\x00\x00\x18ftypmp42")[0] is True
    assert validate_video_signature(b"\x00\x00\x00\x20moov....")[0] is True
    
    # Valid AVI signature
    avi_hdr = b"RIFF\x00\x00\x00\x00AVI LIST"
    assert validate_video_signature(avi_hdr)[0] is True

    # Valid WebM / MKV signature
    webm_hdr = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81"
    assert validate_video_signature(webm_hdr)[0] is True

    # Invalid payloads (plain text, python script, shell script, garbage)
    assert validate_video_signature(b"#!/bin/bash\necho hello")[0] is False
    assert validate_video_signature(b"import os; os.system('ls')")[0] is False
    assert validate_video_signature(b"plain text content")[0] is False
    assert validate_video_signature(b"short")[0] is False


def test_video_upload_corrupt_content_rejected(tmp_path):
    """Corrupt content with an .mp4 extension but invalid binary signature is rejected."""
    storage = VideoStorage(base_dir=tmp_path)
    corrupt_garbage = b"\xde\xad\xbe\xef" * 100
    ok, msg, meta = storage.save_upload(corrupt_garbage, "damaged_stream.mp4")
    assert ok is False
    assert "magic bytes" in msg.lower() or "video format" in msg.lower()
    assert meta == {}


def test_storage_capacity_limit_and_cleanup(tmp_path):
    # Set capacity limit to 5000 bytes
    storage = VideoStorage(base_dir=tmp_path, max_storage_bytes=5000)
    chunk = b"\x00\x00\x00\x18ftypmp42" + (b"A" * 2000)

    # 1. First upload succeeds
    ok1, _, meta1 = storage.save_upload(chunk, "video1.mp4")
    assert ok1 is True

    # 2. Second upload succeeds
    ok2, _, meta2 = storage.save_upload(chunk, "video2.mp4")
    assert ok2 is True

    # 3. Third upload exceeds 5000 bytes limit
    ok3, msg3, _ = storage.save_upload(chunk, "video3.mp4")
    assert ok3 is False
    assert "Storage limit reached" in msg3

    # Check stats
    stats = storage.get_storage_stats()
    assert stats["total_bytes"] > 4000
    assert stats["raw_videos_count"] == 2

    # Prune temp files
    tmp_file = storage.processed_dir / "annotated_123.tmp.mp4"
    tmp_file.write_bytes(b"temp")
    assert tmp_file.exists()
    pruned = storage.prune_temp_files()
    assert pruned == 1
    assert not tmp_file.exists()

    # Cleanup old files
    cleaned = storage.cleanup_old_files(max_age_seconds=0.0)
    assert cleaned >= 2
    assert storage.get_total_storage_bytes() == 0


def test_disk_backed_chunked_upload_lifecycle(tmp_path):
    """Verifies complete disk-backed chunked upload lifecycle with SHA-256 and container verification."""
    import io
    import hashlib

    storage = VideoStorage(base_dir=tmp_path)

    # 3-part video payload: header + payload + trailer
    c1 = b"\x00\x00\x00 ftypisom\x00\x00\x02\x00" + (b"A" * 1000)
    c2 = b"B" * 2000
    c3 = b"C" * 1500
    full_payload = c1 + c2 + c3
    full_sha256 = hashlib.sha256(full_payload).hexdigest()

    # 1. Initialize
    ok, msg, init_meta = storage.init_chunked_upload(
        original_filename="bengaluru_corridor.mp4",
        file_size=len(full_payload),
        total_chunks=3,
        chunk_size=len(c2),
        expected_sha256=full_sha256,
        owner="officer_rajesh"
    )
    assert ok is True
    upload_id = init_meta["upload_id"]
    assert upload_id.startswith("upl_")

    # 2. Upload chunks with status checks
    ok1, _, res1 = storage.save_chunk_stream(upload_id, 0, io.BytesIO(c1), len(c1), requesting_owner="officer_rajesh")
    assert ok1 is True
    assert res1["is_complete"] is False

    ok2, _, res2 = storage.save_chunk_stream(upload_id, 1, io.BytesIO(c2), len(c2), requesting_owner="officer_rajesh")
    assert ok2 is True

    # Check status
    ok_st, _, st = storage.get_chunked_upload_status(upload_id, requesting_owner="officer_rajesh")
    assert ok_st is True
    assert st["uploaded_chunks"] == [0, 1]
    assert st["missing_chunks"] == [2]

    # Upload chunk 2
    ok3, _, res3 = storage.save_chunk_stream(upload_id, 2, io.BytesIO(c3), len(c3), requesting_owner="officer_rajesh")
    assert ok3 is True
    assert res3["is_complete"] is True

    # 3. Finalize
    ok_fin, msg_fin, fin_meta = storage.finalize_chunked_upload(upload_id, requesting_owner="officer_rajesh")
    assert ok_fin is True
    assert "video_id" in fin_meta
    vid = fin_meta["video_id"]
    assert fin_meta["sha256"] == full_sha256
    assert fin_meta["size_bytes"] == len(full_payload)
    assert fin_meta["owner"] == "officer_rajesh"

    # Verify assembled file on disk
    resolved = storage.get_raw_video_path(vid)
    assert resolved is not None
    assert resolved.exists()
    assert resolved.read_bytes() == full_payload

    # Verify chunk session directory was cleaned up
    assert not (storage.chunks_dir / upload_id).exists()


def test_chunked_upload_retry_support(tmp_path):
    """Verifies that re-uploading an existing chunk cleanly overwrites it without error."""
    import io
    storage = VideoStorage(base_dir=tmp_path)
    c1 = b"\x00\x00\x00 ftypisom" + (b"X" * 100)

    ok, _, init_meta = storage.init_chunked_upload("retry_test.mp4", len(c1), 1, owner="user1")
    assert ok is True
    upl_id = init_meta["upload_id"]

    # First attempt
    ok1, _, _ = storage.save_chunk_stream(upl_id, 0, io.BytesIO(c1), len(c1), requesting_owner="user1")
    assert ok1 is True

    # Retry same chunk (e.g. network timeout on client response)
    ok2, msg2, _ = storage.save_chunk_stream(upl_id, 0, io.BytesIO(c1), len(c1), requesting_owner="user1")
    assert ok2 is True
    assert "successfully" in msg2


def test_chunked_upload_ownership_boundary(tmp_path):
    """Verifies cross-user isolation: non-owner cannot upload chunks or finalize upload."""
    import io
    storage = VideoStorage(base_dir=tmp_path)
    c1 = b"\x00\x00\x00 ftypisom" + (b"Z" * 50)

    ok, _, init_meta = storage.init_chunked_upload("alice.mp4", len(c1), 1, owner="alice")
    assert ok is True
    upl_id = init_meta["upload_id"]

    # Bob attempts to upload chunk into Alice's session -> Forbidden
    ok_bob, msg_bob, _ = storage.save_chunk_stream(upl_id, 0, io.BytesIO(c1), len(c1), requesting_owner="bob")
    assert ok_bob is False
    assert "Forbidden" in msg_bob

    # Alice uploads chunk -> Success
    ok_alice, _, _ = storage.save_chunk_stream(upl_id, 0, io.BytesIO(c1), len(c1), requesting_owner="alice")
    assert ok_alice is True

    # Bob attempts to finalize Alice's session -> Forbidden
    ok_fin, msg_fin, _ = storage.finalize_chunked_upload(upl_id, requesting_owner="bob")
    assert ok_fin is False
    assert "Forbidden" in msg_fin


def test_chunked_upload_sha256_mismatch_rejected(tmp_path):
    """Verifies that SHA-256 mismatch halts assembly and unlinks temporary assembly files."""
    import io
    storage = VideoStorage(base_dir=tmp_path)
    c1 = b"\x00\x00\x00 ftypisom" + (b"K" * 100)

    ok, _, init_meta = storage.init_chunked_upload("hash_test.mp4", len(c1), 1, owner="alice")
    upl_id = init_meta["upload_id"]
    storage.save_chunk_stream(upl_id, 0, io.BytesIO(c1), len(c1), requesting_owner="alice")

    # Finalize with incorrect expected hash
    ok_fin, msg_fin, _ = storage.finalize_chunked_upload(
        upl_id, requesting_owner="alice", expected_sha256="deadbeef" * 8
    )
    assert ok_fin is False
    assert "SHA-256 verification failed" in msg_fin

    # Ensure no leftover assembly temp file
    assert len(list(storage.raw_dir.glob("*.assembly.tmp"))) == 0


def test_chunked_upload_missing_chunk_rejected(tmp_path):
    """Verifies that finalize fails if not all chunks are uploaded."""
    import io
    storage = VideoStorage(base_dir=tmp_path)
    c1 = b"\x00\x00\x00 ftypisom" + (b"M" * 100)

    ok, _, init_meta = storage.init_chunked_upload("missing_test.mp4", len(c1) * 2, 2, owner="alice")
    upl_id = init_meta["upload_id"]

    # Only upload chunk 0, chunk 1 is missing
    storage.save_chunk_stream(upl_id, 0, io.BytesIO(c1), len(c1), requesting_owner="alice")

    ok_fin, msg_fin, _ = storage.finalize_chunked_upload(upl_id, requesting_owner="alice")
    assert ok_fin is False
    assert "missing chunk 1" in msg_fin

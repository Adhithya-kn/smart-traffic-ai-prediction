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

"""
tests/test_video_upload.py - Unit Tests for Video Upload and File Persistence
"""

import pytest
from pathlib import Path
from traffic_system.storage.video_storage import VideoStorage


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
    payload = b"test script"
    ok, msg, _ = storage.save_upload(payload, "malicious_script.sh")
    assert ok is False
    assert "Unsupported file extension" in msg


def test_video_upload_size_limit(tmp_path, monkeypatch):
    storage = VideoStorage(base_dir=tmp_path)
    # Monkeypatch max upload size to 1000 bytes
    import traffic_system.storage.video_storage as vs_mod
    monkeypatch.setattr(vs_mod, "MAX_VIDEO_UPLOAD_SIZE", 1000)

    large_payload = b"x" * 1001
    ok, msg, _ = storage.save_upload(large_payload, "large_sample.mp4")
    assert ok is False
    assert "exceeds limit" in msg


def test_video_upload_path_traversal_sanitization(tmp_path):
    storage = VideoStorage(base_dir=tmp_path)
    sample_bytes = b"safe content"
    ok, msg, meta = storage.save_upload(sample_bytes, "../../../etc/cron.d/hack.mp4")
    assert ok is True
    saved_path = Path(meta["file_path"])
    # Confirms it is strictly contained inside the tmp_path uploads folder
    assert saved_path.parent == storage.raw_dir
    assert ".." not in saved_path.name

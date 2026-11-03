"""
traffic_system/storage/video_storage.py - Secure Video File Persistence
Manages video uploads, validated paths, format verification, and processed output persistence.
"""

import os
import uuid
import threading
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from traffic_system.config import (
    VIDEO_STORAGE_DIR,
    MAX_VIDEO_UPLOAD_SIZE,
    ALLOWED_VIDEO_EXTENSIONS
)
from traffic_system.core.fs_utils import (
    sanitize_filename,
    validate_safe_path,
    atomic_write_bytes
)


class VideoStorage:
    """Manages raw uploaded MP4 videos and annotated computer vision outputs."""
    def __init__(self, base_dir: Path = VIDEO_STORAGE_DIR):
        self.base_dir = Path(base_dir).resolve()
        self.raw_dir = self.base_dir / "uploads"
        self.processed_dir = self.base_dir / "processed"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def save_upload(self, data: bytes, original_filename: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates size, extension, and persists uploaded video safely.
        Returns (success, message, metadata).
        """
        if not data:
            return False, "Uploaded file content is empty.", {}

        if len(data) > MAX_VIDEO_UPLOAD_SIZE:
            mb = MAX_VIDEO_UPLOAD_SIZE / (1024 * 1024)
            return False, f"File size exceeds limit of {mb:.0f} MB.", {}

        clean_name = sanitize_filename(original_filename, default="sample_traffic.mp4")
        ext = Path(clean_name).suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            allowed_str = ", ".join(ALLOWED_VIDEO_EXTENSIONS)
            return False, f"Unsupported file extension '{ext}'. Allowed: {allowed_str}.", {}

        video_id = str(uuid.uuid4())[:12]
        dest_filename = f"{video_id}_{clean_name}"
        dest_path = validate_safe_path(self.raw_dir / dest_filename, self.base_dir)

        try:
            atomic_write_bytes(data, dest_path)
        except Exception as e:
            return False, f"Failed to persist video file: {str(e)}", {}

        metadata = {
            "video_id": video_id,
            "filename": clean_name,
            "stored_filename": dest_filename,
            "file_path": str(dest_path),
            "size_bytes": len(data),
            "size_mb": round(len(data) / (1024 * 1024), 2),
            "extension": ext
        }
        return True, "Video uploaded and persisted successfully.", metadata

    def get_raw_video_path(self, video_id_or_filename: str) -> Optional[Path]:
        """Resolves existing raw video file path."""
        with self._lock:
            # Check direct filename
            candidate = (self.raw_dir / video_id_or_filename).resolve()
            if candidate.exists() and candidate.is_file():
                return candidate

            # Check prefix match for video_id
            for p in self.raw_dir.glob(f"{video_id_or_filename}*"):
                if p.is_file():
                    return p
            return None

    def get_processed_video_path(self, job_id: str) -> Optional[Path]:
        """Resolves existing annotated processed video file path."""
        with self._lock:
            for ext in (".mp4", ".avi"):
                candidate = (self.processed_dir / f"annotated_{job_id}{ext}").resolve()
                if candidate.exists() and candidate.is_file():
                    return candidate
            return None

    def create_processed_path(self, job_id: str, ext: str = ".mp4") -> Path:
        """Returns safe output path for annotated video."""
        target = self.processed_dir / f"annotated_{job_id}{ext}"
        return validate_safe_path(target, self.base_dir)

    def delete_video(self, video_id: str) -> bool:
        """Deletes raw and processed files for given video ID."""
        deleted = False
        with self._lock:
            raw = self.get_raw_video_path(video_id)
            if raw and raw.exists():
                raw.unlink()
                deleted = True
            proc = self.get_processed_video_path(video_id)
            if proc and proc.exists():
                proc.unlink()
                deleted = True
        return deleted


_VIDEO_STORAGE: Optional[VideoStorage] = None

def get_video_storage() -> VideoStorage:
    global _VIDEO_STORAGE
    if _VIDEO_STORAGE is None:
        _VIDEO_STORAGE = VideoStorage()
    return _VIDEO_STORAGE

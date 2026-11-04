"""
traffic_system/storage/video_storage.py - Secure Video File Persistence
Manages video uploads, validated paths, format verification, user ownership association,
path containment, and processed output persistence.
"""

import os
import uuid
import hashlib
import threading
import time
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
    is_safe_path,
    is_valid_identifier,
    atomic_write_bytes,
    atomic_json_dump,
    safe_read_json
)


MAX_TOTAL_STORAGE_BYTES = int(os.environ.get("CV_MAX_STORAGE_BYTES", str(5 * 1024 * 1024 * 1024)))  # 5 GB total limit


def validate_video_signature(data: bytes, ext: str = "") -> Tuple[bool, str]:
    """
    Validates genuine video binary header signatures (magic bytes).
    Prevents non-video binaries, scripts, or corrupt headers from being saved.
    Supports MP4/QuickTime (ftyp, moov, mdat), AVI (RIFF...AVI), and WebM/MKV (\x1a\x45\xdf\xa3).
    """
    if not data or len(data) < 8:
        return False, "File is too small to contain a valid video container header."

    # MP4 / MOV / M4V / QuickTime: bytes 4 to 8 contain box types like 'ftyp', 'moov', 'mdat'
    if len(data) >= 8 and data[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip"):
        return True, "Valid MP4/QuickTime container signature."

    # AVI: bytes 0..4 == RIFF and bytes 8..12 == 'AVI '
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return True, "Valid AVI container signature."

    # WebM / MKV (Matroska EBML header): bytes 0..4 == \x1a\x45\xdf\xa3
    if len(data) >= 4 and data[:4] == b"\x1a\x45\xdf\xa3":
        return True, "Valid WebM/MKV container signature."

    return False, "Uploaded file header magic bytes do not match a genuine video format (expected MP4, AVI, or WebM)."


class VideoStorage:
    """
    Manages raw uploaded MP4 videos and annotated computer vision outputs.
    Strictly verifies path containment, binary magic bytes, storage capacity limits,
    and associates video uploads with their owning user.
    """
    def __init__(self, base_dir: Path = VIDEO_STORAGE_DIR, max_storage_bytes: int = MAX_TOTAL_STORAGE_BYTES):
        self.base_dir = Path(base_dir).resolve()
        self.max_storage_bytes = max_storage_bytes
        self.raw_dir = self.base_dir / "uploads"
        self.processed_dir = self.base_dir / "processed"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._load_metadata()

    def _load_metadata(self):
        """Loads metadata sidecars from raw_dir."""
        with self._lock:
            for p in self.raw_dir.glob("*.meta.json"):
                if p.is_file():
                    meta = safe_read_json(p)
                    if isinstance(meta, dict) and "video_id" in meta:
                        self._metadata_cache[meta["video_id"]] = meta

    def save_upload(
        self,
        data: bytes,
        original_filename: str,
        owner: str = ""
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates size, extension, magic bytes signature, storage capacity, and persists video.
        Associates the video with its owning user.
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

        # Validate video binary signature (magic bytes)
        sig_ok, sig_msg = validate_video_signature(data, ext)
        if not sig_ok:
            return False, sig_msg, {}

        # Validate total storage capacity limits
        current_usage = self.get_total_storage_bytes()
        if (current_usage + len(data)) > self.max_storage_bytes:
            limit_gb = self.max_storage_bytes / (1024 ** 3)
            return False, f"Storage limit reached ({limit_gb:.1f} GB capacity exceeded). Please remove old video files.", {}

        video_id = str(uuid.uuid4()).replace("-", "")[:12]
        dest_filename = f"{video_id}_{clean_name}"
        dest_path = validate_safe_path(self.raw_dir / dest_filename, self.raw_dir)

        try:
            atomic_write_bytes(data, dest_path)
        except Exception as e:
            return False, f"Failed to persist video file: {str(e)}", {}

        sha256_hash = hashlib.sha256(data).hexdigest()
        metadata = {
            "video_id": video_id,
            "filename": clean_name,
            "stored_filename": dest_filename,
            "file_path": str(dest_path),
            "size_bytes": len(data),
            "size_mb": round(len(data) / (1024 * 1024), 2),
            "extension": ext,
            "sha256": sha256_hash,
            "owner": owner or "anonymous",
            "created_at": time.time()
        }

        # Persist durable metadata sidecar
        meta_path = dest_path.with_name(f"{dest_filename}.meta.json")
        try:
            atomic_json_dump(metadata, meta_path)
        except Exception:
            pass

        with self._lock:
            self._metadata_cache[video_id] = metadata

        return True, "Video uploaded and persisted successfully.", metadata

    def get_video_owner(self, video_id: str) -> Optional[str]:
        """Returns the username owning the specified video ID."""
        if not is_valid_identifier(video_id):
            return None
        with self._lock:
            if video_id in self._metadata_cache:
                return self._metadata_cache[video_id].get("owner")
            # Attempt to locate on disk
            for p in self.raw_dir.glob(f"{video_id}*.meta.json"):
                meta = safe_read_json(p)
                if isinstance(meta, dict):
                    self._metadata_cache[video_id] = meta
                    return meta.get("owner")
        return None

    def get_raw_video_path(self, video_id_or_filename: str) -> Optional[Path]:
        """
        Resolves existing raw video file path strictly within raw_dir.
        Blocks path traversal attacks.
        """
        if not video_id_or_filename or not isinstance(video_id_or_filename, str):
            return None

        # Disallow directory separators, null bytes, and traversal tokens
        if "/" in video_id_or_filename or "\\" in video_id_or_filename or ".." in video_id_or_filename:
            return None

        with self._lock:
            # Check direct filename
            candidate = (self.raw_dir / video_id_or_filename).resolve()
            try:
                candidate.relative_to(self.raw_dir)
                if candidate.exists() and candidate.is_file() and not candidate.name.endswith(".meta.json"):
                    return candidate
            except (ValueError, RuntimeError):
                return None

            # Check prefix match for valid video_id
            if is_valid_identifier(video_id_or_filename):
                for p in self.raw_dir.glob(f"{video_id_or_filename}*"):
                    try:
                        p.resolve().relative_to(self.raw_dir)
                        if p.is_file() and not p.name.endswith(".meta.json"):
                            return p
                    except (ValueError, RuntimeError):
                        continue

            return None

    def get_processed_video_path(self, job_id: str) -> Optional[Path]:
        """
        Resolves existing annotated processed video file path strictly within processed_dir.
        Blocks path traversal attacks.
        """
        if not is_valid_identifier(job_id):
            return None

        with self._lock:
            for ext in (".mp4", ".avi", ".webm"):
                candidate = (self.processed_dir / f"annotated_{job_id}{ext}").resolve()
                try:
                    candidate.relative_to(self.processed_dir)
                    if candidate.exists() and candidate.is_file():
                        return candidate
                except (ValueError, RuntimeError):
                    continue
            return None

    def create_processed_path(self, job_id: str, ext: str = ".mp4") -> Path:
        """Returns safe output path for annotated video."""
        if not is_valid_identifier(job_id):
            raise ValueError(f"Invalid job_id format: '{job_id}'")
        target = self.processed_dir / f"annotated_{job_id}{ext}"
        return validate_safe_path(target, self.processed_dir)

    def create_temp_processed_path(self, job_id: str, ext: str = ".mp4") -> Path:
        """Returns safe temporary output path for two-phase atomic write."""
        if not is_valid_identifier(job_id):
            raise ValueError(f"Invalid job_id format: '{job_id}'")
        target = self.processed_dir / f"annotated_{job_id}.tmp{ext}"
        return validate_safe_path(target, self.processed_dir)

    def delete_video(self, video_id: str) -> bool:
        """Deletes raw, metadata, and processed files for given video ID."""
        if not is_valid_identifier(video_id):
            return False
        deleted = False
        with self._lock:
            raw = self.get_raw_video_path(video_id)
            if raw and raw.exists():
                raw.unlink(missing_ok=True)
                # Also delete sidecar metadata
                for meta_p in self.raw_dir.glob(f"{video_id}*.meta.json"):
                    meta_p.unlink(missing_ok=True)
                self._metadata_cache.pop(video_id, None)
                deleted = True
            proc = self.get_processed_video_path(video_id)
            if proc and proc.exists():
                proc.unlink(missing_ok=True)
                deleted = True
        return deleted

    def get_total_storage_bytes(self) -> int:
        """Calculates total disk bytes used across raw and processed directories."""
        with self._lock:
            total = 0
            for folder in (self.raw_dir, self.processed_dir):
                if folder.exists():
                    for f in folder.glob("*"):
                        if f.is_file():
                            try:
                                total += f.stat().st_size
                            except OSError:
                                pass
            return total

    def get_storage_stats(self) -> Dict[str, Any]:
        """Returns comprehensive storage metrics."""
        with self._lock:
            raw_bytes = sum(f.stat().st_size for f in self.raw_dir.glob("*") if f.is_file() and not f.name.endswith(".meta.json"))
            proc_bytes = sum(f.stat().st_size for f in self.processed_dir.glob("*") if f.is_file())
            total = raw_bytes + proc_bytes
            return {
                "total_bytes": total,
                "total_mb": round(total / (1024 * 1024), 2),
                "max_capacity_bytes": self.max_storage_bytes,
                "max_capacity_gb": round(self.max_storage_bytes / (1024 ** 3), 2),
                "usage_pct": round((total / max(self.max_storage_bytes, 1)) * 100.0, 1),
                "raw_videos_count": len([f for f in self.raw_dir.glob("*") if f.is_file() and not f.name.endswith(".meta.json")]),
                "processed_videos_count": len(list(self.processed_dir.glob("annotated_*")))
            }

    def cleanup_old_files(self, max_age_seconds: float = 7 * 86400) -> int:
        """
        Removes raw and processed video files older than max_age_seconds.
        Preserves active and recent files. Returns number of files removed.
        """
        now = time.time()
        removed_count = 0
        with self._lock:
            for folder in (self.raw_dir, self.processed_dir):
                if not folder.exists():
                    continue
                for f in folder.glob("*"):
                    if not f.is_file():
                        continue
                    try:
                        mtime = f.stat().st_mtime
                        if (now - mtime) > max_age_seconds:
                            f.unlink(missing_ok=True)
                            removed_count += 1
                    except OSError:
                        continue

            # Reload metadata cache after cleanup
            self._metadata_cache.clear()
            self._load_metadata()
        return removed_count

    def verify_video_integrity(self, video_id: str) -> Tuple[bool, str]:
        """Verifies stored raw video checksum against its persisted metadata sidecar."""
        if not is_valid_identifier(video_id):
            return False, "Invalid video ID format."

        with self._lock:
            meta = self._metadata_cache.get(video_id)
            if not meta:
                raw_p = self.get_raw_video_path(video_id)
                if not raw_p:
                    return False, f"Video {video_id} not found."
                meta_p = self.raw_dir / f"{raw_p.name}.meta.json"
                meta = safe_read_json(meta_p) if meta_p.exists() else None

            if not meta or "sha256" not in meta:
                return True, "No SHA-256 hash in legacy metadata; file exists."

            raw_path = self.get_raw_video_path(video_id)
            if not raw_path or not raw_path.exists():
                return False, "Raw video binary missing on disk."

            try:
                hasher = hashlib.sha256()
                with open(raw_path, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                computed = hasher.hexdigest()
                if computed == meta["sha256"]:
                    return True, f"Integrity verified (SHA-256 match: {computed[:12]}...)."
                return False, f"Integrity check failed: checksum mismatch (expected {meta['sha256'][:8]}, got {computed[:8]})."
            except Exception as e:
                return False, f"Integrity check error: {str(e)}"

    def enforce_retention_policy(self, max_usage_ratio: float = 0.85, max_age_seconds: float = 7 * 86400) -> int:
        """
        Enforces automated retention cleanup:
        1. Prunes files older than max_age_seconds.
        2. If storage usage still exceeds max_usage_ratio, removes oldest files until under threshold.
        Returns total number of files removed.
        """
        removed = self.cleanup_old_files(max_age_seconds=max_age_seconds)
        removed += self.prune_temp_files()

        with self._lock:
            current_bytes = self.get_total_storage_bytes()
            threshold_bytes = int(self.max_storage_bytes * max_usage_ratio)

            if current_bytes > threshold_bytes:
                # Gather all files with mtime
                all_files = []
                for folder in (self.raw_dir, self.processed_dir):
                    if folder.exists():
                        for f in folder.glob("*"):
                            if f.is_file() and not f.name.endswith(".meta.json"):
                                try:
                                    all_files.append((f.stat().st_mtime, f.stat().st_size, f))
                                except OSError:
                                    pass

                # Sort oldest first
                all_files.sort(key=lambda x: x[0])

                for mtime, size, f_path in all_files:
                    if current_bytes <= threshold_bytes:
                        break
                    try:
                        f_path.unlink(missing_ok=True)
                        meta_sidecar = f_path.with_name(f"{f_path.name}.meta.json")
                        meta_sidecar.unlink(missing_ok=True)
                        current_bytes -= size
                        removed += 1
                    except OSError:
                        pass

                self._metadata_cache.clear()
                self._load_metadata()

        return removed

    def prune_temp_files(self) -> int:
        """Removes orphaned temporary processed or upload files (.tmp, .tmp.*)."""
        removed = 0
        with self._lock:
            for folder in (self.raw_dir, self.processed_dir):
                if not folder.exists():
                    continue
                for f in folder.glob("*.tmp*"):
                    if f.is_file():
                        try:
                            f.unlink(missing_ok=True)
                            removed += 1
                        except OSError:
                            pass
        return removed


_VIDEO_STORAGE: Optional[VideoStorage] = None

def get_video_storage() -> VideoStorage:
    global _VIDEO_STORAGE
    if _VIDEO_STORAGE is None:
        _VIDEO_STORAGE = VideoStorage()
    return _VIDEO_STORAGE

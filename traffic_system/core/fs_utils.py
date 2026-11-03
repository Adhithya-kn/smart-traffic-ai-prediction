"""
traffic_system/core/fs_utils.py - Hardened Filesystem Persistence Utilities
POSIX two-phase atomic write with hardware cache flush, path containment validation,
and sandbox-resilient fallbacks.
"""

import os
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

FILENAME_ASCII_STRIP = re.compile(r"[^A-Za-z0-9_.-]")


def sanitize_filename(filename: str, default: str = "upload.bin") -> str:
    """
    Sanitizes candidate filename to eliminate path traversal characters,
    directory separators, and dangerous punctuation.
    """
    if not filename:
        return default
    basename = Path(filename).name
    clean = FILENAME_ASCII_STRIP.sub("_", basename).strip("._")
    return clean if clean else default


def validate_safe_path(path: Path | str, base_dir: Path | str, allow_create: bool = True) -> Path:
    """
    Validates that candidate path resolves strictly within the intended base directory.
    Prevents path traversal attacks (e.g., ../ escaping).
    """
    base = Path(base_dir).resolve()
    candidate = (base / path if not Path(path).is_absolute() else Path(path)).resolve()

    try:
        candidate.relative_to(base)
    except ValueError:
        raise ValueError(f"Path traversal detected: {path} escapes base directory {base}")

    if allow_create and not candidate.parent.exists():
        candidate.parent.mkdir(parents=True, exist_ok=True)

    return candidate


def _sync_fd(fileno: int) -> None:
    """Executes robust hardware-level cache synchronization."""
    if HAS_FCNTL and hasattr(fcntl, "F_FULLFSYNC"):
        try:
            fcntl.fcntl(fileno, fcntl.F_FULLFSYNC)
            return
        except (OSError, AttributeError):
            pass
    try:
        os.fsync(fileno)
    except OSError:
        pass


def atomic_json_dump(data: Any, target_path: Path | str) -> None:
    """
    POSIX Two-Phase Atomic Write for JSON:
    1. Write and hardware-sync to a unique temporary file.
    2. Atomically replace the target file via os.replace.
    Fallback resilience handles restricted sandbox directories gracefully.
    """
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    temp_path = None
    try:
        temp_fd, temp_str = tempfile.mkstemp(dir=str(target.parent), prefix="atomic_json_", suffix=".tmp")
        temp_path = Path(temp_str)
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            _sync_fd(f.fileno())
        os.replace(temp_path, target)
        return
    except (PermissionError, OSError):
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    try:
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            _sync_fd(f.fileno())
    except Exception as e:
        raise OSError(f"Failed to persist atomic JSON to {target}: {e}")


def atomic_write_bytes(data: bytes, target_path: Path | str) -> None:
    """
    POSIX Two-Phase Atomic Write for binary payloads (models, media, archives).
    """
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    temp_path = None
    try:
        temp_fd, temp_str = tempfile.mkstemp(dir=str(target.parent), prefix="atomic_bin_", suffix=".tmp")
        temp_path = Path(temp_str)
        with os.fdopen(temp_fd, "wb") as f:
            f.write(data)
            f.flush()
            _sync_fd(f.fileno())
        os.replace(temp_path, target)
        return
    except (PermissionError, OSError):
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    try:
        with open(target, "wb") as f:
            f.write(data)
            f.flush()
            _sync_fd(f.fileno())
    except Exception as e:
        raise OSError(f"Failed to persist atomic binary to {target}: {e}")


def safe_read_json(target_path: Path | str, default: Any = None) -> Any:
    """Reads JSON file safely, returning default on missing or malformed content."""
    path = Path(target_path)
    if not path.exists() or not path.is_file():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

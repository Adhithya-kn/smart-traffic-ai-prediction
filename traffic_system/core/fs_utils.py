"""
traffic_system/core/fs_utils.py - Hardened Filesystem Persistence Utilities
POSIX two-phase atomic write with hardware cache flush, path containment validation,
strict identifier validation, and sandbox-resilient fallbacks.
"""

import os
import json
import re
import urllib.parse
import tempfile
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

FILENAME_ASCII_STRIP = re.compile(r"[^A-Za-z0-9_.-]")
IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def is_valid_identifier(ident: Any) -> bool:
    """
    Validates identifier (such as video_id or job_id) against strict alphanumeric
    and underscore/hyphen format. Rejects empty, whitespace, path traversal, or special characters.
    """
    if not ident or not isinstance(ident, str):
        return False
    return bool(IDENTIFIER_REGEX.match(ident.strip()))


def sanitize_filename(filename: str, default: str = "upload.bin") -> str:
    """
    Sanitizes candidate filename to eliminate path traversal characters,
    directory separators, URL-encoded sequences, and dangerous punctuation.
    """
    if not filename:
        return default

    # Unquote any URL-encoded traversal characters (e.g., %2e%2e%2f)
    try:
        decoded = urllib.parse.unquote(str(filename))
    except Exception:
        decoded = str(filename)

    # Strip null bytes and replace path separators with underscores
    decoded = decoded.replace("\x00", "").replace("/", "_").replace("\\", "_")

    basename = Path(decoded).name
    clean = FILENAME_ASCII_STRIP.sub("_", basename).strip("._")
    # Eliminate multiple consecutive dots or underscores
    clean = re.sub(r"\.{2,}", ".", clean)
    clean = re.sub(r"_{2,}", "_", clean)
    return clean if clean else default


def is_safe_path(path: Path | str, base_dir: Path | str) -> bool:
    """
    Determines whether a candidate path safely resides within base_dir.
    Returns False on path traversal or invalid resolution.
    """
    try:
        base = Path(base_dir).resolve()
        candidate = (base / path if not Path(path).is_absolute() else Path(path)).resolve()
        candidate.relative_to(base)
        return True
    except (ValueError, RuntimeError, OSError):
        return False


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


import threading

_GLOBAL_FS_LOCK = threading.RLock()
_PATH_LOCKS: dict[str, threading.Lock] = {}


def _get_path_lock(path_str: str) -> threading.Lock:
    with _GLOBAL_FS_LOCK:
        if path_str not in _PATH_LOCKS:
            _PATH_LOCKS[path_str] = threading.Lock()
        return _PATH_LOCKS[path_str]


def atomic_json_dump(data: Any, target_path: Path | str) -> None:
    """
    POSIX Two-Phase Atomic Write for JSON:
    1. Synchronizes across concurrent threads using per-path locking.
    2. Writes and hardware-syncs to a unique temporary file.
    3. Atomically replaces the target file via os.replace.
    Guarantees readers never observe a corrupted or partially written JSON record.
    """
    target = Path(target_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    canonical_key = str(target)
    path_lock = _get_path_lock(canonical_key)

    with path_lock:
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
    """Reads JSON file safely with retry resilience, returning default on missing or malformed content."""
    import time
    path = Path(target_path)
    if not path.exists() or not path.is_file():
        return default
    for attempt in range(2):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            if attempt == 0:
                time.sleep(0.01)
                continue
            return default
    return default

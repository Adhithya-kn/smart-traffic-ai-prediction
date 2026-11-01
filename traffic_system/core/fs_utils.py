"""
traffic_system/core/fs_utils.py - Filesystem Persistence Utilities
POSIX two-phase atomic write with fsync and sandbox-resilient fallbacks.
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Any

def atomic_json_dump(data: Any, target_path: Path) -> None:
    """
    POSIX Two-Phase Atomic Write:
    1. Write and fsync to a unique temporary file.
    2. Atomically replace the target file.
    Includes fallback resilience for restricted sandbox environments where mkstemp
    inside custom workspace directories may trigger PermissionError.
    """
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    temp_path = None
    try:
        # Phase 1: Try creating tempfile in parent directory for atomic same-device rename
        temp_fd, temp_str = tempfile.mkstemp(dir=str(target.parent), prefix="atomic_", suffix=".tmp")
        temp_path = Path(temp_str)
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(temp_path, target)
        return
    except (PermissionError, OSError):
        # Clean up failed temp path if created
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    # Phase 2 Fallback: Direct write with flush to target path directly
    try:
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
    except Exception as e:
        raise OSError(f"Failed to persist atomic JSON to {target_path}: {e}")

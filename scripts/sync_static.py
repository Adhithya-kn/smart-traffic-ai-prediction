#!/usr/bin/env python3
"""
Static Asset Synchronization Utility
Ensures canonical static assets in app/static/ are mirrored to public/ for Vercel/CDN serving.
"""

import sys
import shutil
import hashlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / "app" / "static"
TARGET_DIR = BASE_DIR / "public"


def file_checksum(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def sync_assets(check_only: bool = False) -> bool:
    if not SOURCE_DIR.exists():
        print(f"[ERROR] Source directory does not exist: {SOURCE_DIR}")
        return False

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    mismatches = []

    for src_path in SOURCE_DIR.rglob("*"):
        if src_path.is_file():
            rel_path = src_path.relative_to(SOURCE_DIR)
            dst_path = TARGET_DIR / rel_path

            if not dst_path.exists() or file_checksum(src_path) != file_checksum(dst_path):
                if check_only:
                    mismatches.append(rel_path)
                else:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                    print(f"[SYNCED] {rel_path}")

    if check_only:
        if mismatches:
            print(f"[FAIL] {len(mismatches)} files are out of sync:")
            for m in mismatches:
                print(f"  - {m}")
            return False
        else:
            print("[OK] All static assets in public/ are in sync with app/static/")
            return True

    print(f"[SUCCESS] Static assets successfully synchronized from {SOURCE_DIR} to {TARGET_DIR}")
    return True


if __name__ == "__main__":
    check_mode = "--check" in sys.argv
    success = sync_assets(check_only=check_mode)
    sys.exit(0 if success else 1)

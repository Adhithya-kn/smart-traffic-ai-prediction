#!/usr/bin/env python3
"""
demonstrate_pipeline.py - Root Backward-Compatibility Forwarder

Forwards all calls, imports, and execution to scripts/demonstrate_pipeline.py
to maintain clean repository structure while guaranteeing complete backward
compatibility with existing documentation, CLI commands, and run_system.py.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.demonstrate_pipeline import (
    run_pipeline,
    print_banner,
    format_table,
)

__all__ = ["run_pipeline", "print_banner", "format_table"]

if __name__ == "__main__":
    run_pipeline()

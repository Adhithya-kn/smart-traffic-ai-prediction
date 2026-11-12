#!/usr/bin/env python3
"""
run_server.py - Convenient CLI entry point for local execution.
Defaults to port 8090 (ensuring isolation with Java NRMS on port 8080).
Usage:
    python3 run_server.py
    python3 run_server.py --port 8090
    python3 run_server.py --port 8095 --host 127.0.0.1
"""

import sys
import os
from pathlib import Path

# Ensure working directory is project root
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "--port" not in sys.argv and "-p" not in sys.argv:
    # Default explicitly to port 8090 for non-conflicting local execution
    sys.argv.extend(["--port", os.environ.get("PORT", "8090")])

if __name__ == "__main__":
    from run_system import main
    main()

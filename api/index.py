"""
api/index.py - Vercel Serverless Function & Cloud Function Entrypoint
Routes incoming HTTP requests to TrafficAppServer with idempotent singleton initialization.

Serverless Environment Constraints:
- Ephemeral filesystem: Vercel functions run in a read-only container with temporary storage in /tmp.
- Execution Limits: Bound by maxDuration (up to 60s) and allocated memory (1024 MB).
- Persistent state: File-based databases must fall back safely when running on read-only serverless runtimes.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# On Vercel serverless, ensure temporary directories point to /tmp
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    os.environ.setdefault("PERSISTENT_DATA_DIR", "/tmp/traffic_data")

from app.server import TrafficAppServer

# Idempotently ensure domain models, road network, and security services are initialized
try:
    TrafficAppServer.ensure_initialized()
except Exception as init_err:
    print(f"[WARN] Serverless warm-up initialization notice: {init_err}")


class handler(TrafficAppServer):
    """Vercel Python runtime HTTP request handler interface."""
    pass

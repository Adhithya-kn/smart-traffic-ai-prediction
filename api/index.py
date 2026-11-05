"""
api/index.py - Vercel serverless entrypoint (LIMITED API SURFACE)
=================================================================
This deployment target is intentionally limited. Read this before deploying:

* Vercel grants the function: 4.5 MB request-body cap, 60 s maxDuration,
  1024 MB memory and an ephemeral /tmp filesystem.
* Full Computer-Vision video analysis (8 MB chunked uploads + YOLO inference +
  FFmpeg annotation) is NOT supported on serverless. Use the Docker/Render
  runtime (`Dockerfile` / `render.yaml`) for CV and persistent state.
* This module imports the same application server as the container runtime so
  that non-CV JSON endpoints keep working when the bundle fits. If the heavy ML
  dependencies are unavailable, deployment should keep the static UI from
  `public/` working and surface API errors rather than silently faking data.

Static UI is served by Vercel from `public/` (generated from `app/static/` via
`scripts/sync_static.py`). The rewrites in `vercel.json` map portal routes to
`public/*.html`; only `/api/*` reaches this function.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    # Ephemeral, per-invocation writable state only.
    os.environ.setdefault("PERSISTENT_DATA_DIR", "/tmp/traffic_data")
    os.environ.setdefault("RUNTIME_DATA_DIR", "/tmp/traffic_data/runtime")
    # Stay below the 4.5 MB platform body limit; CV uploads are unsupported here.
    os.environ.setdefault("MAX_REQUEST_BODY_SIZE", "4000000")
    os.environ.setdefault("MAX_VIDEO_UPLOAD_SIZE", "4000000")
    os.environ.setdefault("CHUNK_UPLOAD_SIZE", "4000000")

from app.server import TrafficAppServer

# Idempotently ensure domain models, road network, and security services are initialized
try:
    TrafficAppServer.ensure_initialized()
except Exception as init_err:
    print(f"[WARN] Serverless warm-up initialization notice: {init_err}")


class handler(TrafficAppServer):
    """Vercel Python runtime HTTP request handler interface."""
    pass

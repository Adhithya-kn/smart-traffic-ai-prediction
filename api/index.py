"""
api/index.py - Vercel Serverless Function & Cloud Function Entrypoint
Routes incoming HTTP requests to TrafficAppServer with idempotent singleton initialization.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.server import TrafficAppServer

# Idempotently ensure domain models, road network, and security services are initialized
TrafficAppServer.ensure_initialized()

class handler(TrafficAppServer):
    """Vercel Python runtime HTTP request handler interface."""
    pass

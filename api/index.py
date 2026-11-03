"""
api/index.py - Vercel Serverless Function Entrypoint
Routes incoming HTTP requests to TrafficAppServer.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.server import TrafficAppServer

TrafficAppServer.ensure_initialized()

class handler(TrafficAppServer):
    pass

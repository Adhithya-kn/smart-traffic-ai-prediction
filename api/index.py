"""
api/index.py - Vercel Serverless Function Entrypoint
Routes incoming HTTP requests to TrafficAppServer.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.server import TrafficAppServer

# Initialize domain services and artifacts once per cold start
TrafficAppServer.ensure_initialized()

# Vercel serverless python runner automatically discovers `handler`
class handler(TrafficAppServer):
    pass

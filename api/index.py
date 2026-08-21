"""
Vercel ASGI entry point for Ultron.

Vercel's Python runtime expects a file in /api that exports an ASGI `app`.
We just import the FastAPI app from python/interface/server.py.

Environment variables to set in Vercel dashboard:
  CF_ACCOUNT_ID       — Cloudflare account ID
  CF_API_TOKEN        — Cloudflare API token
  ULTRON_PROJECT_ROOT — /var/task  (set in vercel.json)
  PYTHONPATH          — /var/task  (set in vercel.json)

WebSockets note: Vercel does NOT support WebSockets on serverless functions.
The UI automatically falls back to HTTP polling (/api/command) when the
WebSocket connection fails — this works on Vercel without any code change.
"""

import sys
import os

# Make sure the project root is on the path so all relative imports work
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Import the FastAPI app — all modules initialise at import time
from python.interface.server import app  # noqa: F401

# Vercel expects the ASGI app to be named `app` or `handler`
# `app` is already the correct name from the import above

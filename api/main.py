#!/usr/bin/env python3
"""FastAPI entrypoint for TTS Storyteller API."""

from __future__ import annotations

import os

from api.app import app

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("TTS_HOST") or "0.0.0.0"
    port_str = os.getenv("TTS_PORT") or "8000"
    port = int(port_str)
    uvicorn.run(app, host=host, port=port)

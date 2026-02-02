#!/usr/bin/env python3
"""FastAPI entrypoint for Qwen3-TTS."""

from __future__ import annotations

import os

from api.app import app

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("QWEN3_TTS_HOST", "0.0.0.0")
    port = int(os.getenv("QWEN3_TTS_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

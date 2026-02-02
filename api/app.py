"""FastAPI application setup."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import audio, jobs, pools, stories, voices
from services.jobs import start_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup/shutdown."""
    start_worker()
    yield


app = FastAPI(title="Qwen3-TTS Home API", version="0.1.0", lifespan=lifespan)

_cors_origins_env = os.getenv("QWEN3_TTS_CORS_ORIGINS", "*")
_cors_origins = (
    ["*"]
    if _cors_origins_env == "*"
    else [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else []
)

if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(voices.router)
app.include_router(pools.router)
app.include_router(stories.router)
app.include_router(jobs.router)
app.include_router(audio.router)

"""FastAPI application setup."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import audio, jobs, pools, stories, voices
from lib.database import close_database, init_database
from lib.env import load_env
from services.jobs import recover_jobs_on_startup, start_worker

load_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup/shutdown."""
    # Ensure backend directories exist
    from lib.paths import ensure_backend_directories

    ensure_backend_directories()

    # Initialize database (DATABASE_URL is required)
    await init_database()
    recovered = await recover_jobs_on_startup()
    if recovered > 0:
        print(f"[Jobs] Recovered {recovered} queued jobs from database")

    # Start the job processing worker
    start_worker()

    yield

    # Cleanup
    await close_database()


app = FastAPI(
    title="TTS Storyteller API",
    version="0.1.0",
    description="Multi-backend TTS API supporting Qwen3-TTS and VibeVoice for voice-driven story generation with parallel execution",
    lifespan=lifespan,
)

_cors_origins_env = os.getenv("TTS_CORS_ORIGINS") or "*"
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
        allow_credentials=False,
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

"""FastAPI application setup."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import audio, jobs, pools, stories, voices
from lib.database import close_database, init_database
from lib.env import load_env
from services.jobs import recover_jobs_on_startup, start_worker

logger = logging.getLogger(__name__)

load_env()

# Root logger config so service/lib loggers are visible under uvicorn
# (uvicorn only configures its own uvicorn.* loggers).
logging.basicConfig(
    level=os.getenv("TTS_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup/shutdown."""
    # Ensure backend directories exist
    from lib.paths import ensure_backend_directories

    ensure_backend_directories()

    # Initialize database (DATABASE_URL is required)
    await init_database()
    stale = await recover_jobs_on_startup()
    if stale > 0:
        logger.info("Marked %d stale job(s) from a previous run as failed", stale)

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


# pools before voices: /voices/pools must not be captured by /voices/{voiceId}
app.include_router(pools.router)
app.include_router(voices.router)
app.include_router(stories.router)
app.include_router(jobs.router)
app.include_router(audio.router)

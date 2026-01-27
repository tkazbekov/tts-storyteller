#!/usr/bin/env python3
"""FastAPI application for Qwen3-TTS story management and generation."""

import asyncio
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from qwen_tts import Qwen3TTSModel

from lib.generation import generate_story_audio
from lib.models import GenerateRequest, Job, ResolvedLine, StoryTemplate, Voice
from lib.paths import get_story_full_audio_path
from lib.resolution import resolve_story
from lib.storage import (
    get_available_voice_ids,
    get_voice_info,
    list_stories,
    load_story,
    save_story,
    voice_has_prompt,
)
from lib.validation import validate_story
from scripts.common import load_tts_model

# Global model cache
_model_cache: Qwen3TTSModel | None = None
_model_config: dict[str, str] = {
    "model": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "device": "cuda:0",
    "dtype": "bfloat16",
    "attn": "auto",
}


def get_or_load_model() -> Qwen3TTSModel:
    """Get cached model or load if not cached."""
    global _model_cache
    if _model_cache is None:
        _model_cache = load_tts_model(
            _model_config["model"],
            _model_config["device"],
            _model_config["dtype"],
            _model_config["attn"],
        )
    return _model_cache


# In-memory job storage (keyed by job ID)
JOBS: dict[str, Job] = {}

# Background task queue (simple single-worker queue)
_job_queue: asyncio.Queue = asyncio.Queue()
_processing_job: str | None = None


async def process_job_queue():
    """Background task processor for generation jobs."""
    global _processing_job

    while True:
        try:
            job_id = await _job_queue.get()
            _processing_job = job_id

            job = JOBS.get(job_id)
            if not job:
                _processing_job = None
                continue

            # Update status to running
            job.status = "running"
            job.message = "Generating audio..."

            try:
                # Validate storyId is present
                if not job.storyId:
                    raise ValueError("Job missing storyId")

                # Load story and resolve
                story = load_story(job.storyId)
                available_voices = get_available_voice_ids()
                resolved_lines = resolve_story(story, available_voices)

                # Get request parameters
                request_params = job.requestParams or {}
                concat = request_params.get("concat", True)
                language = "English"  # Default language

                # Get cached model
                tts_model = get_or_load_model()

                # Generate audio in thread pool to avoid blocking event loop
                output_path = await asyncio.to_thread(
                    generate_story_audio,
                    resolved_lines=resolved_lines,
                    story_id=job.storyId,
                    tts_model=tts_model,
                    language=language,
                    concat=concat,
                )

                # Update job with success
                job.status = "succeeded"
                job.message = "Generation completed"
                job.outputPath = str(output_path)

            except Exception as e:
                # Update job with error
                job.status = "failed"
                job.message = str(e)

            finally:
                _processing_job = None
                _job_queue.task_done()

        except Exception as e:
            # Log error but continue processing
            print(f"Error processing job: {e}")
            _processing_job = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup/shutdown."""
    # Startup: start background job processor
    asyncio.create_task(process_job_queue())
    yield
    # Shutdown: cleanup if needed (currently nothing to clean up)


app = FastAPI(title="Qwen3-TTS Home API", version="0.1.0", lifespan=lifespan)

# Enable CORS for mobile web app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local/home use - adjust if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/voices")
def list_voices() -> list[Voice]:
    """List all available voices."""
    voice_ids = get_available_voice_ids()
    voices = []

    for voice_id in sorted(voice_ids):
        info = get_voice_info(voice_id)
        if info:
            voices.append(Voice(**info))

    return voices


@app.get("/voices/{voiceId}")
def get_voice(voiceId: str) -> Voice:
    """Get voice details by ID."""
    if not voice_has_prompt(voiceId):
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    info = get_voice_info(voiceId)
    if not info:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    return Voice(**info)


@app.get("/stories")
def list_stories_endpoint() -> list[str]:
    """List all story IDs."""
    return list_stories()


@app.post("/stories", status_code=201)
def create_story_endpoint(story: StoryTemplate) -> StoryTemplate:
    """Create a new story template."""
    # Validate story structure
    errors = validate_story(story.model_dump())
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # Validate voice IDs exist
    available_voices = get_available_voice_ids()
    if story.defaultVoiceId not in available_voices:
        raise HTTPException(
            status_code=400,
            detail=f"defaultVoiceId '{story.defaultVoiceId}' not found in available voices",
        )

    # Generate ID from title (sanitize)
    story_id = re.sub(r"[^a-z0-9_-]", "", story.title.lower().replace(" ", "_"))
    if not story_id:
        story_id = "story"

    # Check if story already exists
    try:
        load_story(story_id)
        raise HTTPException(status_code=409, detail=f"Story '{story_id}' already exists")
    except FileNotFoundError:
        pass

    # Save story
    save_story(story_id, story)
    return story


@app.get("/stories/{storyId}")
def get_story_endpoint(storyId: str) -> StoryTemplate:
    """Get story template by ID."""
    try:
        return load_story(storyId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None


@app.put("/stories/{storyId}")
def replace_story_endpoint(storyId: str, story: StoryTemplate) -> StoryTemplate:
    """Replace an existing story template."""
    # Validate story structure
    errors = validate_story(story.model_dump())
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # Validate voice IDs exist
    available_voices = get_available_voice_ids()
    if story.defaultVoiceId not in available_voices:
        raise HTTPException(
            status_code=400,
            detail=f"defaultVoiceId '{story.defaultVoiceId}' not found in available voices",
        )

    # Check if story exists
    try:
        load_story(storyId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None

    # Save story
    save_story(storyId, story)
    return story


@app.post("/stories/{storyId}/render")
def render_story_endpoint(storyId: str) -> list[ResolvedLine]:
    """Resolve roles to voices for a story."""
    try:
        story = load_story(storyId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None

    available_voices = get_available_voice_ids()

    try:
        resolved = resolve_story(story, available_voices)
        return resolved
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/stories/{storyId}/generate", status_code=202)
def generate_story_endpoint(
    storyId: str,
    request: GenerateRequest | None = None,
) -> Job:
    """Start audio generation for a story."""
    # Check if story exists
    try:
        load_story(storyId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None

    # Create job with request parameters
    job_id = str(uuid.uuid4())
    request_params = request.model_dump() if request else {}
    job = Job(
        id=job_id,
        type="generate",
        status="queued",
        storyId=storyId,
        message="Job queued",
        outputPath=None,
        requestParams=request_params,
    )

    JOBS[job_id] = job

    # Queue job for processing
    _job_queue.put_nowait(job_id)

    return job


@app.get("/jobs/{jobId}")
def get_job_endpoint(jobId: str) -> Job:
    """Get job status by ID."""
    job = JOBS.get(jobId)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{jobId}' not found")
    return job


@app.get("/audio/stories/{storyId}/full.wav")
def get_story_audio(storyId: str) -> FileResponse:
    """Download the concatenated audio file for a story."""
    audio_path = get_story_full_audio_path(storyId)

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio for story '{storyId}' not found")

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=f"{storyId}_full.wav",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

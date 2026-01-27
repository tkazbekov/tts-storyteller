#!/usr/bin/env python3
"""FastAPI application for Qwen3-TTS story management and generation."""

import asyncio
import os
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from qwen_tts import Qwen3TTSModel

from lib.generation import generate_story_audio
from lib.models import (
    GenerateRequest,
    Job,
    ResolvedLine,
    StoryTemplate,
    Voice,
    VoiceConfig,
    VoicePool,
)
from lib.paths import get_story_full_audio_path, get_story_output_dir
from lib.resolution import resolve_story
from lib.storage import (
    delete_voice_config,
    get_all_pools,
    get_available_voice_ids,
    get_voice_info,
    get_voices_by_pool,
    list_stories,
    load_pools_config,
    load_story,
    load_voice_config,
    remove_voice_from_all_pools,
    save_pools_config,
    save_story,
    save_voice_config,
    voice_has_prompt,
)
from lib.validation import validate_story
from lib.voice_generation import generate_voice
from lib.voice_metadata import should_regenerate_voice
from scripts.common import load_tts_model

# Global model cache
_model_cache: Qwen3TTSModel | None = None
_voice_design_model_cache: Qwen3TTSModel | None = None
_model_config: dict[str, str] = {
    "model": os.getenv("QWEN3_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-Base"),
    "device": os.getenv("QWEN3_TTS_DEVICE", "cuda:0"),
    "dtype": os.getenv("QWEN3_TTS_DTYPE", "bfloat16"),
    "attn": os.getenv("QWEN3_TTS_ATTN", "auto"),
}
_voice_design_model_config: dict[str, str] = {
    "model": os.getenv("QWEN3_TTS_VOICE_DESIGN_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"),
    "device": os.getenv("QWEN3_TTS_DEVICE", "cuda:0"),
    "dtype": os.getenv("QWEN3_TTS_DTYPE", "bfloat16"),
    "attn": os.getenv("QWEN3_TTS_ATTN", "auto"),
}


def get_or_load_model() -> Qwen3TTSModel:
    """Get cached Base model or load if not cached."""
    global _model_cache
    if _model_cache is None:
        _model_cache = load_tts_model(
            _model_config["model"],
            _model_config["device"],
            _model_config["dtype"],
            _model_config["attn"],
        )
    return _model_cache


def get_or_load_voice_design_model() -> Qwen3TTSModel:
    """Get cached VoiceDesign model or load if not cached."""
    global _voice_design_model_cache
    if _voice_design_model_cache is None:
        _voice_design_model_cache = load_tts_model(
            _voice_design_model_config["model"],
            _voice_design_model_config["device"],
            _voice_design_model_config["dtype"],
            _voice_design_model_config["attn"],
        )
    return _voice_design_model_cache


# In-memory job storage (keyed by job ID)
JOBS: dict[str, Job] = {}

# Track which story has an active job (running or queued)
# Maps storyId -> jobId
_story_active_jobs: dict[str, str] = {}

# Track which voice has an active job (running or queued)
# Maps voiceId -> jobId
_voice_active_jobs: dict[str, str] = {}

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

            # Track active jobs
            if job.storyId:
                _story_active_jobs[job.storyId] = job_id
                job.message = "Generating audio..."
            elif job.voiceId:
                _voice_active_jobs[job.voiceId] = job_id
                job.message = "Generating voice..."

            try:
                if job.type == "voice_generate":
                    # Voice generation job
                    if not job.voiceId:
                        raise ValueError("Job missing voiceId")

                    # Get voice config from request params
                    request_params = job.requestParams or {}
                    voice_config_dict = request_params.get("voice_config")
                    if not voice_config_dict:
                        raise ValueError("Job missing voice_config in requestParams")

                    voice_config = VoiceConfig(**voice_config_dict)

                    # Get models
                    voice_design_model = get_or_load_voice_design_model()
                    base_model = get_or_load_model()

                    # Generate voice in thread pool to avoid blocking event loop
                    wav_path, prompt_path = await asyncio.to_thread(
                        generate_voice,
                        voice_id=job.voiceId,
                        voice_config=voice_config,
                        voice_design_model=voice_design_model,
                        base_model=base_model,
                        force_regenerate=False,
                    )

                    # Update voices.json
                    save_voice_config(job.voiceId, voice_config)

                    # Update job with success
                    job.status = "succeeded"
                    job.message = "Voice generation completed"
                    job.outputPath = str(prompt_path)

                elif job.type == "generate":
                    # Story generation job
                    if not job.storyId:
                        raise ValueError("Job missing storyId")

                    # Load story and resolve
                    story = load_story(job.storyId)
                    available_voices = get_available_voice_ids()
                    resolved_lines = resolve_story(story, available_voices)

                    # Get language from story template (defaults to "English")
                    language = story.language

                    # Get request parameters
                    request_params = job.requestParams or {}
                    concat = request_params.get("concat", True)

                    # Automatically use incremental generation if metadata exists
                    # Check if we have previous generation metadata
                    from lib.metadata import find_changed_indices, load_line_hashes

                    regenerate_indices: set[int] | None = None
                    if load_line_hashes(job.storyId) is not None:
                        # Metadata exists - use incremental generation
                        changed_indices = find_changed_indices(
                            job.storyId, resolved_lines, language
                        )
                        regenerate_indices = changed_indices
                    # If no metadata exists, regenerate_indices stays None (full generation)

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
                        regenerate_indices=regenerate_indices,
                    )

                    # Save metadata for future incremental generation
                    from lib.metadata import save_line_hashes

                    save_line_hashes(job.storyId, resolved_lines, language)

                    # Update job with success
                    job.status = "succeeded"
                    job.message = "Generation completed"
                    # Store the path: file path if concatenated, directory path if not
                    job.outputPath = str(output_path)
                else:
                    raise ValueError(f"Unknown job type: {job.type}")

            except Exception as e:
                # Update job with error
                job.status = "failed"
                job.message = str(e)

            finally:
                # Clear tracking when job completes
                if job.storyId and _story_active_jobs.get(job.storyId) == job_id:
                    _story_active_jobs.pop(job.storyId, None)
                if job.voiceId and _voice_active_jobs.get(job.voiceId) == job_id:
                    _voice_active_jobs.pop(job.voiceId, None)
                _processing_job = None
                _job_queue.task_done()

        except Exception as e:
            # Log error but continue processing
            print(f"Error processing job: {e}")
            # Clear tracking on error
            if _processing_job:
                job = JOBS.get(_processing_job)
                if job:
                    if job.storyId and _story_active_jobs.get(job.storyId) == _processing_job:
                        _story_active_jobs.pop(job.storyId, None)
                    if job.voiceId and _voice_active_jobs.get(job.voiceId) == _processing_job:
                        _voice_active_jobs.pop(job.voiceId, None)
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
# CORS origins: comma-separated list, or "*" for all, or empty for no CORS
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


@app.get("/voices")
def list_voices(pool: str | None = None) -> list[Voice]:
    """
    List all available voices, optionally filtered by pool.

    Args:
        pool: Optional pool name to filter voices
    """
    if pool:
        voice_ids = set(get_voices_by_pool(pool))
    else:
        voice_ids = get_available_voice_ids()

    voices = []
    for voice_id in sorted(voice_ids):
        info = get_voice_info(voice_id)
        if info:
            voices.append(Voice(**info))

    return voices


@app.get("/voices/{voiceId}")
def get_voice_endpoint(voiceId: str) -> Voice:
    """Get voice details by ID."""
    if not voice_has_prompt(voiceId):
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    info = get_voice_info(voiceId)
    if not info:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    return Voice(**info)


@app.post("/voices", status_code=202)
def create_voice_endpoint(voice_config: VoiceConfig) -> Job:
    """
    Create a new voice.

    Generates WAV and prompt files, updates voices.json.
    Returns a job ID to track generation progress.
    """
    # Check if voice already exists
    existing = load_voice_config(voice_config.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Voice '{voice_config.id}' already exists")

    # Check if job is already running for this voice
    if voice_config.id in _voice_active_jobs:
        raise HTTPException(
            status_code=409,
            detail=f"Voice '{voice_config.id}' is already being generated",
        )

    # Create job
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        type="voice_generate",
        status="queued",
        storyId=None,
        voiceId=voice_config.id,
        message="Queued for generation",
        outputPath=None,
        requestParams={"voice_config": voice_config.model_dump()},
    )
    JOBS[job_id] = job

    # Queue job
    _voice_active_jobs[voice_config.id] = job_id
    _job_queue.put_nowait(job_id)

    return job


@app.put("/voices/{voiceId}")
def update_voice_endpoint(voiceId: str, voice_config: VoiceConfig) -> Job | VoiceConfig:
    """
    Update an existing voice configuration.

    If config changed, triggers regeneration job.
    Otherwise, just updates voices.json.
    """
    # Check if voice exists
    existing = load_voice_config(voiceId)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    # Ensure IDs match
    if voice_config.id != voiceId:
        raise HTTPException(status_code=400, detail="voiceId in path must match id in body")

    # Check if regeneration is needed
    needs_regeneration = should_regenerate_voice(voiceId, voice_config)

    # Update voices.json immediately
    save_voice_config(voiceId, voice_config)

    # If config changed, trigger regeneration job
    if needs_regeneration:
        # Check if job is already running
        if voiceId in _voice_active_jobs:
            raise HTTPException(
                status_code=409,
                detail=f"Voice '{voiceId}' is already being generated",
            )

        # Create regeneration job
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            type="voice_generate",
            status="queued",
            storyId=None,
            voiceId=voiceId,
            message="Queued for regeneration",
            outputPath=None,
            requestParams={"voice_config": voice_config.model_dump()},
        )
        JOBS[job_id] = job

        # Queue job
        _voice_active_jobs[voiceId] = job_id
        _job_queue.put_nowait(job_id)

        return job

    # No regeneration needed, return updated config
    return voice_config


@app.delete("/voices/{voiceId}", status_code=204)
def delete_voice_endpoint(voiceId: str) -> None:
    """
    Delete a voice.

    Removes from voices.json and all pools.
    Does not delete WAV or prompt files.
    """
    # Check if voice exists
    existing = load_voice_config(voiceId)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    # Check if job is running
    if voiceId in _voice_active_jobs:
        raise HTTPException(
            status_code=409, detail=f"Voice '{voiceId}' is currently being generated"
        )

    # Remove from voices.json
    delete_voice_config(voiceId)

    # Remove from all pools
    remove_voice_from_all_pools(voiceId)


@app.get("/voices/pools")
def list_pools_endpoint() -> list[str]:
    """List all available voice pools."""
    return sorted(get_all_pools())


@app.get("/voices/pools/{poolName}")
def get_pool_endpoint(poolName: str) -> list[Voice]:
    """Get all voices in a pool."""
    voice_ids = get_voices_by_pool(poolName)
    if not voice_ids:
        raise HTTPException(status_code=404, detail=f"Pool '{poolName}' not found")

    voices = []
    for voice_id in sorted(voice_ids):
        info = get_voice_info(voice_id)
        if info:
            voices.append(Voice(**info))

    return voices


@app.post("/voices/pools/{poolName}", status_code=201)
def create_pool_endpoint(poolName: str, pool: VoicePool) -> VoicePool:
    """Create a new pool."""
    if pool.name != poolName:
        raise HTTPException(status_code=400, detail="poolName in path must match name in body")

    pools = load_pools_config()
    if poolName in pools:
        raise HTTPException(status_code=409, detail=f"Pool '{poolName}' already exists")

    # Validate voice IDs exist
    available_voices = get_available_voice_ids()
    for voice_id in pool.voiceIds:
        if voice_id not in available_voices:
            raise HTTPException(
                status_code=400,
                detail=f"Voice '{voice_id}' not found in available voices",
            )

    pools[poolName] = pool.voiceIds
    save_pools_config(pools)

    return pool


@app.put("/voices/pools/{poolName}")
def update_pool_endpoint(poolName: str, pool: VoicePool) -> VoicePool:
    """Update an existing pool."""
    if pool.name != poolName:
        raise HTTPException(status_code=400, detail="poolName in path must match name in body")

    pools = load_pools_config()
    if poolName not in pools:
        raise HTTPException(status_code=404, detail=f"Pool '{poolName}' not found")

    # Validate voice IDs exist
    available_voices = get_available_voice_ids()
    for voice_id in pool.voiceIds:
        if voice_id not in available_voices:
            raise HTTPException(
                status_code=400,
                detail=f"Voice '{voice_id}' not found in available voices",
            )

    pools[poolName] = pool.voiceIds
    save_pools_config(pools)

    return pool


@app.delete("/voices/pools/{poolName}", status_code=204)
def delete_pool_endpoint(poolName: str) -> None:
    """Delete a pool."""
    pools = load_pools_config()
    if poolName not in pools:
        raise HTTPException(status_code=404, detail=f"Pool '{poolName}' not found")

    del pools[poolName]
    save_pools_config(pools)


@app.get("/stories")
def list_stories_endpoint() -> list[str]:
    """List all story IDs."""
    return list_stories()


@app.post("/stories", status_code=201)
def create_story_endpoint(story: StoryTemplate) -> StoryTemplate:
    """
    Create a new story template.

    Voice assignment: Use the `casting` field to map roleIds (as strings) to voiceIds.
    Resolution order: line.actorId → casting[roleId] → defaultVoiceId

    Example casting: {"0": "narrator_male", "1": "woman"} assigns roleId 0 to narrator_male, roleId 1 to woman.
    """
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
    """
    Resolve roles to voices for a story.

    Returns a preview of voice assignments showing which voice will be used for each line.
    Resolution order: line.actorId → casting[roleId] → defaultVoiceId

    Use this endpoint to verify voice assignments before generating audio.
    """
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
    """
    Start audio generation for a story.

    Only one job per story can be running or queued at a time.
    If a job is already active for this story, returns 409 Conflict.
    """
    # Check if story exists
    try:
        load_story(storyId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None

    # Check if there's already an active job for this story
    existing_job_id = _story_active_jobs.get(storyId)
    if existing_job_id:
        existing_job = JOBS.get(existing_job_id)
        if existing_job and existing_job.status in ("queued", "running"):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Job already active for story '{storyId}'. "
                    f"Existing job ID: {existing_job_id}, status: {existing_job.status}. "
                    "Wait for the current job to complete or cancel it before starting a new one."
                ),
            )

    # Create job with request parameters
    job_id = str(uuid.uuid4())
    request_params = request.model_dump() if request else {}
    job = Job(
        id=job_id,
        type="generate",
        status="queued",
        storyId=storyId,
        voiceId=None,
        message="Job queued",
        outputPath=None,
        requestParams=request_params,
    )

    JOBS[job_id] = job

    # Track that this story has a queued job
    _story_active_jobs[storyId] = job_id

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
    """
    Download the concatenated audio file for a story.

    Note: This endpoint only works if the story was generated with `concat: true`.
    If `concat: false`, individual audio files are in the output directory but
    no concatenated file exists. Use `/audio/stories/{storyId}/files` to list individual files.
    """
    audio_path = get_story_full_audio_path(storyId)

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio for story '{storyId}' not found. "
            "This endpoint requires the story to be generated with 'concat: true'. "
            "Check the job's outputPath for individual audio files location, "
            "or use GET /audio/stories/{storyId}/files to list available files.",
        )

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=f"{storyId}_full.wav",
    )


@app.get("/audio/stories/{storyId}/files")
def list_story_audio_files(storyId: str) -> list[str]:
    """
    List all individual audio files for a story.

    Returns a list of filenames in the story's output directory.
    These are the individual line audio files (e.g., "001_narrator_male.wav").
    """
    output_dir = get_story_output_dir(storyId)

    if not output_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Output directory for story '{storyId}' not found. "
            "The story may not have been generated yet.",
        )

    # List all .wav files in the directory, sorted
    wav_files = sorted([f.name for f in output_dir.glob("*.wav")])

    if not wav_files:
        raise HTTPException(
            status_code=404,
            detail=f"No audio files found for story '{storyId}'.",
        )

    return wav_files


@app.get("/audio/stories/{storyId}/files/{filename}")
def get_story_audio_file(storyId: str, filename: str) -> FileResponse:
    """
    Download a specific individual audio file for a story.

    Use GET /audio/stories/{storyId}/files to list available filenames.
    """
    output_dir = get_story_output_dir(storyId)
    audio_path = output_dir / filename

    # Security: ensure the file is within the output directory
    try:
        audio_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid filename: '{filename}'",
        ) from None

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio file '{filename}' not found for story '{storyId}'.",
        ) from None

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=filename,
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("QWEN3_TTS_HOST", "0.0.0.0")
    port = int(os.getenv("QWEN3_TTS_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
